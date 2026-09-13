"""Test bootstrap — runs before any test module import.

Phase 0 stubs never call the LLM, but config.py reads LLM_API_KEY at import;
tests stay hermetic with a dummy value (unit tests never hit the network).
"""

import os

import pytest

os.environ.setdefault("LLM_API_KEY", "test-key")


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
