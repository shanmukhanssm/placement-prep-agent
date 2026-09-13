"""Test bootstrap — runs before any test module import.

Phase 2 nodes call the LLM through ``config.call_structured`` → ``config.get_llm``;
tests stay hermetic by monkeypatching ``config.get_llm`` to canned per-role queues
(unit tests never hit the network, code-standards.md).
"""

import os

import pytest

import prep_agent.config as config
from prep_agent.state import Profile
from prep_agent.tools.report_card import (
    InitReportCardArgs,
    WriteProfileArgs,
    init_report_card,
    write_profile,
)

os.environ.setdefault("LLM_API_KEY", "test-key")

VALID_PROFILE: dict[str, object] = {
    "name": "Arjun",
    "degree_branch": "B.Tech CSE",
    "grad_year": 2027,
    "target_roles": ["SDE"],
    "weak_areas": ["arrays"],
    "core_subject": "aiml",
}


class StubLLM:
    """Offline stand-in for ChatOpenAI — canned outputs popped per call.

    Structured calls go through ``with_structured_output(schema).invoke(prompt)`` and
    are validated against the REAL pydantic schema (so schema drift fails tests).
    A queued ``Exception`` instance raises — the canned judge-failure path.
    """

    def __init__(self, queue: list[object], role: str) -> None:
        self.queue = queue
        self.role = role
        self.prompts: list[str] = []

    def with_structured_output(self, schema: type) -> object:  # noqa: ANN001
        llm = self

        class _Structured:
            def invoke(self, prompt: str) -> object:
                llm.prompts.append(prompt)
                if not llm.queue:
                    raise RuntimeError(f"[llm:{llm.role}] canned queue empty")
                out = llm.queue.pop(0)
                if isinstance(out, Exception):
                    raise out
                return schema.model_validate(out)

        return _Structured()

    def invoke(self, prompt: str) -> object:  # plain-text calls (comm wrap summary)
        self.prompts.append(prompt)
        if not self.queue:
            raise RuntimeError(f"[llm:{self.role}] canned queue empty")
        out = self.queue.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


@pytest.fixture(autouse=True)
def _hermetic_cwd(tmp_path, monkeypatch):
    """Run every test with CWD at a per-test tmp directory.

    Since the Phase 0↔1 merge the specialist wrap nodes call the REAL
    save_session_results, which writes data/history/... relative to CWD
    (config.DATA_DIR). This keeps that I/O out of the repo — the tmp_path
    rule from code-standards.md, applied suite-wide. Unit tests redirect
    DATA_DIR explicitly anyway; e2e's SQLite checkpointer already uses an
    absolute tmp path, so nothing else is CWD-sensitive.
    """
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def llm_queues(monkeypatch) -> dict[str, list[object]]:
    """Patch config.get_llm → per-role StubLLM queues. Seed a queue with
    ``llm_queues["dsa_evaluator"] = [{...}, Exception("boom"), ...]``."""
    queues: dict[str, list[object]] = {}

    def _fake_get_llm(role: str) -> StubLLM:
        return StubLLM(queues.setdefault(role, []), role)

    monkeypatch.setattr(config, "get_llm", _fake_get_llm)
    return queues


@pytest.fixture
def seeded_card() -> None:
    """A valid profile + empty report card in the tmp data dir — wrap nodes can save."""
    assert write_profile(WriteProfileArgs(profile=dict(VALID_PROFILE)))
    assert init_report_card(InitReportCardArgs(profile=dict(VALID_PROFILE)))


@pytest.fixture
def profile_obj() -> Profile:
    return Profile.model_validate(VALID_PROFILE)
