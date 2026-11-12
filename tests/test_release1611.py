import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop"))
from engine_api import EngineAPI
from learning_calendar.focus import DEFAULT_COMMENTS
from learning_calendar.local_backup import read_backup


def test_comments_preserve_running_clock_restart_and_backup(tmp_path, monkeypatch):
    now = [100.0]
    monkeypatch.setattr("learning_calendar.focus.time.monotonic", lambda: now[0])
    api = EngineAPI(tmp_path)
    api.dispatch("focus.command", dict(action="start"))
    now[0] += 30
    comments = dict(heading="오직 지금", focus_end="집중 완료", break_end="다시 시작")
    state = api.dispatch("focus.command", dict(action="comments", comments=comments))
    assert state["running"] and state["elapsed"] == 30 and state["duration"] == 1500
    assert state["comments"] == comments
    backup = tmp_path / "focus.calix"
    api.dispatch("backup.export", dict(path=str(backup.resolve())))
    assert read_backup(backup)["focus_comments"] == comments
    api.dispatch("focus.command", dict(action="comments", comments=dict(heading="", focus_end="", break_end="")))
    assert api.dispatch("focus.state", {})["comments"]["heading"] == ""
    api.dispatch("backup.restore", dict(path=str(backup.resolve())))
    assert api.dispatch("focus.state", {})["comments"] == comments
    api.close()
    api = EngineAPI(tmp_path)
    try:
        assert api.dispatch("focus.state", {})["comments"] == comments
    finally:
        api.close()


@pytest.mark.parametrize("comments", [None, {}, dict(DEFAULT_COMMENTS, heading="x" * 81), dict(DEFAULT_COMMENTS, focus_end="x" * 121), dict(DEFAULT_COMMENTS, focus_end=1), dict(DEFAULT_COMMENTS, heading="a\nb"), dict(DEFAULT_COMMENTS, break_end="\ud800")])
def test_invalid_comments_do_not_change_saved_text(tmp_path, comments):
    api = EngineAPI(tmp_path)
    try:
        with pytest.raises(ValueError):
            api.dispatch("focus.command", dict(action="comments", comments=comments))
        assert api.dispatch("focus.state", {})["comments"] == DEFAULT_COMMENTS
    finally:
        api.close()
