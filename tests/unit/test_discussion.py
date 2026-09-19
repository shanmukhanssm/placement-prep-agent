"""Fix-cycle pins — discussion intent, clarify escalation cap, syllabus blurb leniency.

Live failures these tests lock down (owner's session transcript):
1. "discuss about the prediction why are you skipping it" misrouted core_subject
   and launched a viva uninvited → the discussion intent + branch now exist.
2. Two consecutive clarifies then a third re-ask (the clarify loop) → clarify
   escalates to an honest answer at clarify_streak >= 2.
3. Syllabus generation died on a missing topics.N.blurb → the blurb is now
   optional and filled deterministically.
Graph wiring (edge table + compiled nodes) is pinned so the branch can't rot.
"""

import json

import pytest

from prep_agent.nodes.greetings import clarify, discussion
from prep_agent.state import IntentClassification, MainState

pytestmark = [pytest.mark.unit]


# --- state schema ---


def test_intent_schema_accepts_discussion() -> None:
    assert IntentClassification(intent="discussion", confidence=0.8).intent == "discussion"


# --- discussion node ---


def test_discussion_node_answers_via_llm(llm_queues) -> None:
    llm_queues["discussion"] = [
        "Honest take: predictions like that are bets, not facts. Best hedge is skill depth."
    ]
    state = MainState(user_message="what do you think about the 2030 jobs prediction")
    out = discussion(state)
    assert out["assistant_message"] == (
        "Honest take: predictions like that are bets, not facts. Best hedge is skill depth."
    )
    assert "session_active" not in out  # a plain conversation handler — never opens a session


def test_discussion_llm_failure_falls_back_honestly(llm_queues) -> None:
    llm_queues["discussion"] = [Exception("boom")]
    out = discussion(MainState(user_message="will robots take my job"))
    # the fallback re-anchors to the tracks instead of bluffing an opinion
    assert "dsa" in out["assistant_message"].lower()
    assert "core subject" in out["assistant_message"].lower()


def test_discussion_prompt_carries_no_trend_numbers() -> None:
    # number-integrity: no numerals injected → nothing to misquote
    from prep_agent.prompts.greetings import DISCUSSION_V1

    rendered = DISCUSSION_V1.format(user_message="what do you think about X")
    assert "{trend_summary_json}" not in rendered


# --- graph wiring ---


def test_discussion_branch_is_wired() -> None:
    from prep_agent.graph import _BRANCHES, build_graph

    assert _BRANCHES["discussion"] == "discussion"
    build_graph()  # compile() validates wiring — an orphan branch would raise


# --- clarify escalation cap ---


class _CapturingLLM:
    """Minimal get_llm stand-in that records the prompt and returns canned text."""

    def __init__(self, captured: dict[str, str], reply: str) -> None:
        self._captured = captured
        self._reply = reply

    def invoke(self, prompt: str) -> str:
        self._captured["prompt"] = prompt
        return self._reply


def test_clarify_uses_normal_prompt_below_streak(monkeypatch) -> None:
    import prep_agent.config as config

    captured: dict[str, str] = {}
    monkeypatch.setattr(
        config, "get_llm", lambda role: _CapturingLLM(captured, "Which track?")
    )
    state = MainState(user_message="hmm ok", clarify_streak=0)
    out = clarify(state)
    assert "Ask ONE short clarifying question" in captured["prompt"]
    assert "do NOT ask again" not in captured["prompt"]
    assert out["assistant_message"] == "Which track?"


def test_clarify_escalates_at_streak_two(monkeypatch) -> None:
    import prep_agent.config as config

    captured: dict[str, str] = {}
    monkeypatch.setattr(
        config,
        "get_llm",
        lambda role: _CapturingLLM(captured, "Honest answer: yes, with caveats. Track?"),
    )
    state = MainState(user_message="just answer me", clarify_streak=2)
    out = clarify(state)
    assert "do NOT ask again" in captured["prompt"]  # the escalate variant
    assert "Ask ONE short clarifying question" not in captured["prompt"]
    assert "Honest answer" in out["assistant_message"]


# --- greet identity path (v3-rev: persona line alone drowned the answer) ---


def test_greet_identity_ask_uses_dedicated_prompt(monkeypatch) -> None:
    import prep_agent.config as config
    from prep_agent.nodes.greetings import greet_returning
    from prep_agent.state import Profile

    captured: dict[str, str] = {}
    monkeypatch.setattr(
        config, "get_llm", lambda role: _CapturingLLM(captured, f"I'm your placement-prep coach, {role}.")
    )
    profile = Profile.model_validate(
        {
            "name": "Arjun",
            "degree_branch": "B.Tech CSE",
            "grad_year": 2027,
            "target_roles": ["SDE"],
            "weak_areas": ["arrays"],
            "core_subject": "DBMS and Operating Systems",
        }
    )
    state = MainState(
        user_message="who are you exactly?",
        profile=profile,
        has_profile=True,
        clarify_streak=0,
    )
    out = greet_returning(state)
    # the identity prompt ANSWERS the ask first and interpolates the core subject;
    # the placeholder is consumed by .format(), so assert on the rendered body
    assert "Answer the identity ask in ONE short line FIRST" in captured["prompt"]
    assert "DBMS and Operating Systems" in captured["prompt"]
    assert "coach" in out["assistant_message"].lower()


def test_greet_normal_message_keeps_standard_prompt(monkeypatch) -> None:
    import prep_agent.config as config
    from prep_agent.nodes.greetings import greet_returning
    from prep_agent.state import Profile

    captured: dict[str, str] = {}
    monkeypatch.setattr(config, "get_llm", lambda role: _CapturingLLM(captured, "Welcome back!"))
    profile = Profile.model_validate(
        {
            "name": "Arjun",
            "degree_branch": "B.Tech CSE",
            "grad_year": 2027,
            "target_roles": ["SDE"],
            "weak_areas": ["arrays"],
            "core_subject": "DBMS",
        }
    )
    state = MainState(user_message="hi, what's up?", profile=profile, has_profile=True)
    greet_returning(state)
    # identity prompt NOT selected — only its body carries this line (persona is shared)
    assert "Answer the identity ask in ONE short line FIRST" not in captured["prompt"]


# --- syllabus blurb leniency ---


def test_ensure_syllabus_fills_missing_blurb_instead_of_failing(tmp_path, monkeypatch) -> None:
    """The live qwen slip (topics.5.blurb Field required) must not fail the call."""
    from prep_agent.tools import syllabus as syllabus_module

    monkeypatch.setattr(syllabus_module, "DATA_DIR", str(tmp_path))
    llm_queues_local: dict[str, list[object]] = {}

    class _Stub:
        def __init__(self, queue: list[object]) -> None:
            self.queue = queue

        def bind_tools(self, tools: list[type], **kwargs: object) -> object:  # noqa: ANN001
            schema = tools[0]
            outer = self

            class _Bound:
                def invoke(self, prompt: str) -> object:
                    out = outer.queue.pop(0)
                    if isinstance(out, Exception):
                        raise out
                    return schema.model_validate(out)

            return _Bound()

    def _fake_call_structured(role: str, schema: type, prompt: str) -> object:
        stub = _Stub(llm_queues_local.setdefault(role, []))
        bound = stub.bind_tools([schema])
        return bound.invoke(prompt)

    monkeypatch.setattr(syllabus_module, "call_structured", _fake_call_structured)
    llm_queues_local["core_syllabus"] = [
        {"topics": [{"name": f"topic {i}"} for i in range(1, 8)]}  # NO blurb anywhere
    ]
    topics = syllabus_module.ensure_syllabus("software engineering")
    assert len(topics) == 7
    assert all(name and blurb for name, blurb in topics)
    payload = json.loads((tmp_path / "syllabus" / "software-engineering.json").read_text())
    assert payload["source"] == "llm"  # NOT the fallback — the real topics survived
