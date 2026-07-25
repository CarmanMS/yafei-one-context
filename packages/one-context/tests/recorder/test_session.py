"""Session state machine + on-disk layout tests (Phase 2.8 M1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from one_context.recorder.session import (
    SessionAlreadyActive,
    SessionNotFound,
    SkillNotFound,
    abort_session,
    get_active_session_id,
    is_external_tool,
    load_session,
    record_cc_session_id,
    recorder_root,
    save_session,
    start_session,
)


# ── start_session ────────────────────────────────────────────────────────


def test_start_session_creates_layout(
    recorder_tmp: Path, repo_with_skill: Path
) -> None:
    sess = start_session("demo", "scenario-a", repo_root=repo_with_skill)

    assert sess.status == "recording"
    assert sess.skill_name == "demo"
    assert sess.scenario_name == "scenario-a"
    assert sess.cc_session_id is None

    sdir = Path(sess.recording_dir)
    assert sdir.exists()
    assert sdir.parent == recorder_root()
    assert (sdir / "session.json").is_file()
    assert (sdir / "rounds.jsonl").is_file()
    assert (sdir / "rounds.jsonl").read_text() == ""
    assert (sdir / "workspace").is_dir()
    assert list((sdir / "workspace").iterdir()) == []

    active_payload = json.loads((recorder_root() / "active.json").read_text())
    assert active_payload["session_id"] == sess.session_id
    assert active_payload["skill_name"] == "demo"


def test_start_session_records_cc_session_id(
    recorder_tmp: Path, repo_with_skill: Path
) -> None:
    sess = start_session(
        "demo", "scn", cc_session_id="cc-abc-123", repo_root=repo_with_skill
    )
    assert sess.cc_session_id == "cc-abc-123"
    on_disk = load_session(sess.session_id)
    assert on_disk.cc_session_id == "cc-abc-123"


def test_start_session_unknown_skill_raises(
    recorder_tmp: Path, tmp_path: Path
) -> None:
    empty_repo = tmp_path / "empty"
    empty_repo.mkdir()
    with pytest.raises(SkillNotFound):
        start_session("ghost", "scn", repo_root=empty_repo)
    # No active session should have been registered.
    assert get_active_session_id() is None


def test_start_session_when_already_active_raises(
    recorder_tmp: Path, repo_with_skill: Path
) -> None:
    first = start_session("demo", "scn1", repo_root=repo_with_skill)
    with pytest.raises(SessionAlreadyActive) as exc_info:
        start_session("demo", "scn2", repo_root=repo_with_skill)
    assert exc_info.value.active_session_id == first.session_id


def test_start_session_rejects_empty_skill_name(recorder_tmp: Path) -> None:
    with pytest.raises(ValueError):
        start_session("", "scn")


# ── abort_session ────────────────────────────────────────────────────────


def test_abort_session_clears_active_and_removes_dir(
    recorder_tmp: Path, repo_with_skill: Path
) -> None:
    sess = start_session("demo", "scn", repo_root=repo_with_skill)
    sdir = Path(sess.recording_dir)
    assert sdir.exists()

    out = abort_session(sess.session_id)

    assert "aborted_at" in out
    assert out["kept_paths"] == []
    assert not sdir.exists()
    assert get_active_session_id() is None


def test_abort_session_keep_staging_preserves_dir(
    recorder_tmp: Path, repo_with_skill: Path
) -> None:
    sess = start_session("demo", "scn", repo_root=repo_with_skill)
    sdir = Path(sess.recording_dir)

    out = abort_session(sess.session_id, keep_staging=True)

    assert out["kept_paths"] == [str(sdir)]
    assert sdir.exists()
    assert (sdir / "session.json").exists()
    persisted = load_session(sess.session_id)
    assert persisted.status == "aborted"
    assert get_active_session_id() is None


def test_abort_unknown_session_raises(recorder_tmp: Path) -> None:
    with pytest.raises(SessionNotFound):
        abort_session("nonexistent-session-id")


def test_abort_after_new_session_only_clears_matching_active(
    recorder_tmp: Path, repo_with_skill: Path
) -> None:
    """Aborting an old session must NOT wipe an unrelated active.json.

    Defensive: abort_session inspects active.json by session_id before
    clearing; an old session_id paired with someone else's active lock
    should leave the lock alone.
    """
    sess1 = start_session("demo", "scn1", repo_root=repo_with_skill)
    abort_session(sess1.session_id, keep_staging=True)  # active.json now cleared
    sess2 = start_session("demo", "scn2", repo_root=repo_with_skill)

    abort_session(sess1.session_id, keep_staging=True)  # again
    # sess2 must still be the active session
    assert get_active_session_id() == sess2.session_id


# ── load/save roundtrip ─────────────────────────────────────────────────


def test_load_session_returns_persisted_state(
    recorder_tmp: Path, repo_with_skill: Path
) -> None:
    sess = start_session("demo", "scn", repo_root=repo_with_skill)
    sess.status = "finalizing"
    save_session(sess)

    reloaded = load_session(sess.session_id)
    assert reloaded.status == "finalizing"
    assert reloaded.skill_name == "demo"
    assert reloaded.scenario_name == "scn"


# ── M8: parent_cc_session_id + cc_session_id backfill ──────────────────


def test_start_session_records_parent_cc_session_id(
    recorder_tmp: Path, repo_with_skill: Path
) -> None:
    sess = start_session(
        "demo",
        "scn",
        repo_root=repo_with_skill,
        parent_cc_session_id="parent-abc",
    )
    assert sess.parent_cc_session_id == "parent-abc"
    on_disk = json.loads((Path(sess.recording_dir) / "session.json").read_text())
    assert on_disk["parent_cc_session_id"] == "parent-abc"
    active = json.loads((recorder_root() / "active.json").read_text())
    assert active["parent_cc_session_id"] == "parent-abc"


def test_load_session_tolerates_pre_m8_session_json(
    recorder_tmp: Path, repo_with_skill: Path
) -> None:
    """Forward-compat: M1-era session.json lacked parent_cc_session_id."""
    sess = start_session("demo", "scn", repo_root=repo_with_skill)
    session_file = Path(sess.recording_dir) / "session.json"
    data = json.loads(session_file.read_text())
    data.pop("parent_cc_session_id", None)
    data["future_field_we_dont_know"] = "should-be-ignored"
    session_file.write_text(json.dumps(data))

    reloaded = load_session(sess.session_id)
    assert reloaded.parent_cc_session_id is None
    assert reloaded.skill_name == "demo"


def test_record_cc_session_id_backfills_when_unset(
    recorder_tmp: Path, repo_with_skill: Path
) -> None:
    sess = start_session("demo", "scn", repo_root=repo_with_skill)
    assert sess.cc_session_id is None

    record_cc_session_id(sess.session_id, "child-xyz")

    reloaded = load_session(sess.session_id)
    assert reloaded.cc_session_id == "child-xyz"
    active = json.loads((recorder_root() / "active.json").read_text())
    assert active["cc_session_id"] == "child-xyz"


def test_record_cc_session_id_is_noop_when_already_set(
    recorder_tmp: Path, repo_with_skill: Path
) -> None:
    sess = start_session(
        "demo", "scn", cc_session_id="already-set", repo_root=repo_with_skill
    )
    record_cc_session_id(sess.session_id, "would-overwrite")

    reloaded = load_session(sess.session_id)
    assert reloaded.cc_session_id == "already-set"


def test_record_cc_session_id_missing_session_swallows(
    recorder_tmp: Path,
) -> None:
    # Must never raise — hook invariant relies on it.
    record_cc_session_id("does-not-exist", "child-xyz")


def test_record_cc_session_id_ignores_empty_value(
    recorder_tmp: Path, repo_with_skill: Path
) -> None:
    sess = start_session("demo", "scn", repo_root=repo_with_skill)
    record_cc_session_id(sess.session_id, "")
    reloaded = load_session(sess.session_id)
    assert reloaded.cc_session_id is None


# ── is_external_tool ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "tool_name, expected",
    [
        ("WebFetch", True),
        ("WebSearch", True),
        ("Bash", True),
        ("mcp__plugin_playwright_playwright__browser_navigate", True),
        ("mcp__onecxt_recorder__start_recording", True),
        ("Read", False),
        ("Write", False),
        ("Edit", False),
        ("Grep", False),
        ("Glob", False),
        ("TodoWrite", False),
        ("Skill", False),
        ("", False),
    ],
)
def test_is_external_tool_classification(tool_name: str, expected: bool) -> None:
    assert is_external_tool(tool_name) is expected


# ── Phase 2.8 M5: stale lock auto-recovery + old dir purge ──────────────


def _seed_active_session(
    recorder_tmp: Path,
    *,
    cc_session_id: str | None,
    started_at_iso: str,
    session_id: str = "stale-uuid-1234",
) -> Path:
    """Manually plant an active.json + session.json without going through
    start_session (which would refuse if lock present)."""
    recorder_tmp.mkdir(parents=True, exist_ok=True)
    sdir = recorder_tmp / session_id
    sdir.mkdir()
    (sdir / "rounds.jsonl").touch()
    (sdir / "workspace").mkdir()
    (sdir / "session.json").write_text(json.dumps({
        "session_id": session_id,
        "skill_name": "demo",
        "scenario_name": "scn",
        "cc_session_id": cc_session_id,
        "started_at": started_at_iso,
        "status": "recording",
        "recording_dir": str(sdir),
        "parent_cc_session_id": None,
    }), encoding="utf-8")
    (recorder_tmp / "active.json").write_text(json.dumps({
        "session_id": session_id,
        "skill_name": "demo",
        "scenario_name": "scn",
        "cc_session_id": cc_session_id,
        "started_at": started_at_iso,
    }), encoding="utf-8")
    return sdir


def test_start_session_auto_recovers_stale_lock_when_started_at_too_old(
    recorder_tmp: Path,
    repo_with_skill: Path,
) -> None:
    """active.json with started_at >6h ago → auto-aborted, new session ok."""
    from datetime import datetime, timezone, timedelta
    very_old = (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat()
    _seed_active_session(recorder_tmp, cc_session_id=None, started_at_iso=very_old)

    # Should NOT raise SessionAlreadyActive; old lock auto-cleared.
    sess = start_session("demo", "scn-new", repo_root=repo_with_skill)
    assert sess.scenario_name == "scn-new"
    # New active.json points at the new session, not the stale one.
    active = json.loads((recorder_tmp / "active.json").read_text())
    assert active["session_id"] == sess.session_id


def test_start_session_auto_recovers_when_session_json_orphaned(
    recorder_tmp: Path,
    repo_with_skill: Path,
) -> None:
    """active.json refers to a session whose dir is gone → clear + proceed."""
    recorder_tmp.mkdir(parents=True, exist_ok=True)
    (recorder_tmp / "active.json").write_text(json.dumps({
        "session_id": "ghost-no-dir",
        "skill_name": "demo",
        "scenario_name": "x",
        "cc_session_id": None,
        "started_at": "2020-01-01T00:00:00+00:00",
    }), encoding="utf-8")

    sess = start_session("demo", "scn-new", repo_root=repo_with_skill)
    assert sess.scenario_name == "scn-new"


def test_start_session_refuses_when_lock_is_fresh(
    recorder_tmp: Path,
    repo_with_skill: Path,
) -> None:
    """Fresh active session (started just now) still blocks new start."""
    from datetime import datetime, timezone
    fresh = datetime.now(timezone.utc).isoformat()
    _seed_active_session(recorder_tmp, cc_session_id=None, started_at_iso=fresh)
    with pytest.raises(SessionAlreadyActive):
        start_session("demo", "scn-new", repo_root=repo_with_skill)


def test_start_session_recovers_when_transcript_stale(
    recorder_tmp: Path,
    repo_with_skill: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """cc transcript file mtime >10m ago → session considered stale."""
    import os
    import time
    from datetime import datetime, timezone

    # Fake ~/.claude/projects/<hash>/<cc_sid>.jsonl with an old mtime.
    fake_home = tmp_path / "home"
    proj_dir = fake_home / ".claude" / "projects" / "fake-hash"
    proj_dir.mkdir(parents=True)
    cc_sid = "cc-stale-session"
    transcript = proj_dir / f"{cc_sid}.jsonl"
    transcript.write_text("{}\n", encoding="utf-8")
    old_mtime = time.time() - 20 * 60  # 20m ago > 10m threshold
    os.utime(transcript, (old_mtime, old_mtime))
    monkeypatch.setenv("HOME", str(fake_home))

    # active.json started_at recent — only transcript staleness should drive.
    _seed_active_session(
        recorder_tmp, cc_session_id=cc_sid,
        started_at_iso=datetime.now(timezone.utc).isoformat(),
    )
    sess = start_session("demo", "scn-new", repo_root=repo_with_skill)
    assert sess.scenario_name == "scn-new"


def test_start_session_purges_old_session_dirs(
    recorder_tmp: Path,
    repo_with_skill: Path,
) -> None:
    """Dirs older than 30 days get rmtree'd; <30 day dirs survive."""
    import os
    import time

    recorder_tmp.mkdir(parents=True, exist_ok=True)
    young = recorder_tmp / "young-session-uuid"
    old = recorder_tmp / "old-session-uuid"
    young.mkdir()
    old.mkdir()
    (young / "marker").touch()
    (old / "marker").touch()
    # Touch old to 31 days ago, young to 5 days ago.
    now = time.time()
    os.utime(old, (now - 31 * 86400, now - 31 * 86400))
    os.utime(young, (now - 5 * 86400, now - 5 * 86400))

    start_session("demo", "scn-fresh", repo_root=repo_with_skill)
    assert not old.exists(), "30+ day old dir should have been purged"
    assert young.exists(), "5 day old dir must survive purge"


def test_start_session_force_overrides_fresh_lock(
    recorder_tmp: Path,
    repo_with_skill: Path,
) -> None:
    """force=True must abort even a brand-new active session.

    Use case: user closes their cc window, immediately opens a new one
    and triggers re-recording. Transcript mtime is still recent so the
    stale heuristic alone would refuse — force=True bypasses it."""
    from datetime import datetime, timezone
    fresh = datetime.now(timezone.utc).isoformat()
    sdir_old = _seed_active_session(
        recorder_tmp, cc_session_id="cc-fresh",
        started_at_iso=fresh, session_id="fresh-uuid-aaaa",
    )

    sess = start_session(
        "demo", "scn-new", repo_root=repo_with_skill, force=True,
    )
    assert sess.scenario_name == "scn-new"
    # Old session's staging dir survived (force=True keeps it).
    assert sdir_old.exists(), "force should keep_staging=True for forensics"
    # Old session status flipped to aborted on disk.
    old_meta = json.loads((sdir_old / "session.json").read_text())
    assert old_meta["status"] == "aborted"


def test_start_session_force_false_still_blocks_on_fresh_lock(
    recorder_tmp: Path,
    repo_with_skill: Path,
) -> None:
    """force=False (explicit opt-out) preserves the original strict block."""
    from datetime import datetime, timezone
    fresh = datetime.now(timezone.utc).isoformat()
    _seed_active_session(recorder_tmp, cc_session_id=None, started_at_iso=fresh)
    with pytest.raises(SessionAlreadyActive):
        start_session(
            "demo", "scn-new", repo_root=repo_with_skill, force=False,
        )


def test_start_session_purge_skips_active_session(
    recorder_tmp: Path,
    repo_with_skill: Path,
) -> None:
    """Purge must never delete the currently-active session dir, even if
    its mtime got nudged to look old."""
    import os
    import time

    # Plant a stale active that will be recovered (auto-aborted) first,
    # then we want to verify the NEW active session won't be purged on a
    # second start_session call.
    sess = start_session("demo", "scn-1", repo_root=repo_with_skill)
    # Touch the session dir to 40 days ago — but it's currently active.
    very_old = time.time() - 40 * 86400
    os.utime(sess.dir, (very_old, very_old))

    # Trigger a second start_session via auto-recovery path: first abort
    # the fresh one to free the lock, then start.
    abort_session(sess.session_id)
    # Re-create active by starting another — but the previous dir is
    # still on disk and "looks" old. Purge should clear it now (no
    # longer active).
    start_session("demo", "scn-2", repo_root=repo_with_skill)
    assert not sess.dir.exists(), (
        "previously-active-but-now-aborted dir aged 40d should be purged "
        "on the next start"
    )
