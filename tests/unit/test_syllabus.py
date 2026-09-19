"""Change-1 pin tests — free-text core subject + the syllabus cache tool.

Covers: canonical_subject aliasing; ensure_syllabus curated short-circuit; LLM
generation cached (second call never touches the LLM); LLM-down deterministic
fallback cached with source=fallback; free-text subjects survive _build_profile.
All file I/O lands in the tmp data dir (hermetic-CWD + DATA_DIR redirect).
"""

import json

import pytest

from prep_agent.prompts.core_subject import AIML_SYLLABUS, CYBER_SYLLABUS
from prep_agent.state import Profile
from prep_agent.tools.syllabus import canonical_subject, ensure_syllabus, subject_label

pytestmark = [pytest.mark.unit]


@pytest.fixture
def syllabus_dir(tmp_path, monkeypatch):
    """Redirect the syllabus tool's DATA_DIR to a tmp directory (unit-conftest pattern)."""
    from prep_agent.tools import syllabus as syllabus_module

    monkeypatch.setattr(syllabus_module, "DATA_DIR", str(tmp_path))
    return tmp_path / "syllabus"


# --- canonical_subject / subject_label ---


def test_canonical_subject_resolves_curated_aliases() -> None:
    assert canonical_subject("AIML") == "aiml"
    assert canonical_subject("AI/ML") == "aiml"
    assert canonical_subject("machine learning") == "aiml"
    assert canonical_subject("ai") == "aiml"  # open question: bare alias now resolves
    assert canonical_subject("Cyber Security") == "cyber"
    assert canonical_subject("cyber") == "cyber"
    assert canonical_subject("infosec") == "cyber"


def test_canonical_subject_keeps_free_text() -> None:
    assert canonical_subject("DBMS") == "DBMS"
    assert canonical_subject("operating systems") == "operating systems"


def test_subject_label_display_names() -> None:
    assert subject_label("aiml") == "AIML"
    assert subject_label("cyber") == "cybersecurity"
    assert subject_label("DBMS") == "DBMS"


# --- ensure_syllabus ---


def test_ensure_syllabus_short_circuits_curated_subjects(syllabus_dir, llm_queues) -> None:
    assert ensure_syllabus("aiml") == AIML_SYLLABUS
    assert ensure_syllabus("cyber") == CYBER_SYLLABUS
    # curated paths never touch the LLM and never write cache files
    assert not syllabus_dir.exists()


def test_ensure_syllabus_generates_and_caches(syllabus_dir, llm_queues) -> None:
    generated = {
        "topics": [
            {"name": f"topic {i}", "blurb": f"depth ceiling {i}"} for i in range(1, 8)
        ]
    }
    llm_queues["core_syllabus"] = [generated]
    first = ensure_syllabus("dbms")
    assert ("topic 1", "depth ceiling 1") in first
    cache_files = list(syllabus_dir.glob("*.json"))
    assert len(cache_files) == 1
    payload = json.loads(cache_files[0].read_text())
    assert payload["source"] == "llm"
    assert payload["subject"] == "dbms"

    # second call is a pure cache hit — the LLM queue still holds its sentinel
    llm_queues["core_syllabus"].append({"topics": generated["topics"]})
    second = ensure_syllabus("dbms")
    assert second == first
    assert len(llm_queues["core_syllabus"]) == 1  # sentinel untouched → no LLM call


def test_ensure_syllabus_falls_back_when_llm_down_and_caches_fallback(
    syllabus_dir, llm_queues
) -> None:
    llm_queues["core_syllabus"] = [Exception("boom"), Exception("boom again")]
    topics = ensure_syllabus("operating systems")
    assert len(topics) >= 6
    assert all("operating systems" in blurb for _, blurb in topics)
    payload = json.loads((syllabus_dir / "operating-systems.json").read_text())
    assert payload["source"] == "fallback"


def test_ensure_syllabus_falls_back_on_thin_llm_output(syllabus_dir, llm_queues) -> None:
    # two topics is below the 6 minimum → the whole call degrades to the fallback
    llm_queues["core_syllabus"] = [
        {"topics": [{"name": "a", "blurb": "b"}, {"name": "c", "blurb": "d"}]}
    ]
    topics = ensure_syllabus("computer networks")
    assert len(topics) >= 6
    assert json.loads((syllabus_dir / "computer-networks.json").read_text())["source"] == (
        "fallback"
    )


def test_ensure_syllabus_fills_missing_blurb_instead_of_failing(syllabus_dir, llm_queues) -> None:
    # Fix (live qwen slip): topics.N.blurb missing must NOT fail the whole call —
    # the schema tolerates it and ensure_syllabus fills the blank deterministically
    llm_queues["core_syllabus"] = [
        {"topics": [{"name": f"topic {i}"} for i in range(1, 8)]}  # no blurb keys at all
    ]
    topics = ensure_syllabus("software engineering")
    assert len(topics) == 7
    assert all(name and blurb for name, blurb in topics)
    payload = json.loads((syllabus_dir / "software-engineering.json").read_text())
    assert payload["source"] == "llm"  # the real topics survived — not the fallback


# --- free-text subjects flow through the Profile (state change pin) ---


def test_profile_accepts_free_text_core_subject(profile_dict) -> None:
    profile_dict["core_subject"] = "dbms"
    profile = Profile.model_validate(profile_dict)
    assert profile.core_subject == "dbms"


def test_profile_rejects_empty_core_subject(profile_dict) -> None:
    from pydantic import ValidationError

    profile_dict["core_subject"] = ""
    with pytest.raises(ValidationError):
        Profile.model_validate(profile_dict)


def test_build_profile_carries_free_text_subject() -> None:
    from prep_agent.nodes.onboarding import _build_profile

    collected = {
        "name": "Arjun",
        "degree_branch": "B.Tech CSE",
        "grad_year": "2027",
        "target_roles": "SDE",
        "weak_areas": "arrays",
        "core_subject": "dbms",
    }
    assert _build_profile(collected).core_subject == "dbms"
