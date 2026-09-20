"""Harden H1 — CLI thread persistence: a restarted CLI resumes the SAME thread.

Companion tests for ``__main__._load_or_mint_thread_id`` (kill-and-resume contract):
the pointer file survives process death in ``data/cli-thread.txt``, so restart
reopens the checkpointed conversation; ``--new`` mints and re-points. The module
imports ``prep_agent.graph`` eagerly, so each test imports it AFTER chdir into a
per-test tmp dir (the studio graph would otherwise create ``data/`` in the repo
root at collection time).
"""

from pathlib import Path


def _cli():
    import prep_agent.__main__ as cli  # noqa: PLC0415 — import AFTER chdir (see module doc)

    return cli


def test_restart_reuses_persisted_thread_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cli = _cli()
    first = cli._load_or_mint_thread_id()
    assert first.startswith("cli:")
    pointer = Path("data/cli-thread.txt")
    assert pointer.read_text(encoding="utf-8").strip() == first
    # a restarted CLI re-calls the same function — it must land on the same thread
    assert cli._load_or_mint_thread_id() == first


def test_fresh_thread_mints_new_id_and_repoints(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cli = _cli()
    old = cli._load_or_mint_thread_id()
    new = cli._load_or_mint_thread_id(fresh=True)
    assert new != old
    assert cli._load_or_mint_thread_id() == new  # pointer now serves the new thread


def test_missing_pointer_mints_and_persists(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cli = _cli()
    assert not Path("data").exists()  # no data dir yet — must not raise
    minted = cli._load_or_mint_thread_id()
    assert minted.startswith("cli:")
    assert Path("data/cli-thread.txt").read_text(encoding="utf-8").strip() == minted
