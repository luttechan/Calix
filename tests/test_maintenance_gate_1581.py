import json
import sqlite3
import sys
import threading
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop"))
from engine_api import EngineAPI
from engine_maintenance import maintain
from learning_calendar.incremental import KEY
from learning_calendar.preferences import read_settings


def test_previous_developer_setting_does_not_bypass_new_warning(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(dict(developer_mode=True)), encoding="utf-8")
    assert read_settings(path)["developer_mode"] is False
    api = EngineAPI(tmp_path)
    try:
        with pytest.raises(ValueError, match="Acknowledge"):
            api.dispatch("preferences.save", dict(developer_mode=True))
    finally:
        api.close()


@pytest.mark.parametrize("action", ["integrity", "clear_sync_cache", "optimize"])
def test_maintenance_preserves_records_and_saves_recovery_before_writes(
    tmp_path, action
):
    api = EngineAPI(tmp_path)
    try:
        api.store.set_meta(KEY, '{"2":"' + "a" * 64 + '"}')
        api.store.set_meta("keep", "unchanged")
        before = api.bootstrap()
        result = maintain(api.store.path, action)
        assert result["healthy"] is True
        assert api.store.get_meta("keep") == "unchanged"
        assert api.bootstrap()["events"] == before["events"]
        if action == "integrity":
            assert "recovery_file" not in result
        else:
            backup = tmp_path / result["recovery_file"]
            assert backup.is_file()
            db = sqlite3.connect(backup)
            try:
                assert db.execute(
                    "SELECT value FROM meta WHERE key=?", (KEY,)
                ).fetchone()[0]
            finally:
                db.close()
        if action == "clear_sync_cache":
            assert not api.store.get_meta(KEY)
    finally:
        api.close()


def test_cancelled_maintenance_never_changes_cache(tmp_path):
    api = EngineAPI(tmp_path)
    try:
        api.store.set_meta(KEY, "original")
        event = threading.Event()
        event.set()
        with pytest.raises(ValueError):
            maintain(api.store.path, "clear_sync_cache", event)
        assert api.store.get_meta(KEY) == "original"
    finally:
        api.close()


def test_database_reset_also_removes_developer_recovery(tmp_path):
    api = EngineAPI(tmp_path)
    try:
        result = maintain(api.store.path, "optimize")
        assert (tmp_path / result["recovery_file"]).is_file()
        from engine_reset import reset_data

        reset_data(api)
        assert not (tmp_path / "developer-recovery").exists()
    finally:
        api.close()
