import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop"))
from engine_api import EngineAPI
from engine_diagnostics import Diagnostics


def test_developer_mode_is_opt_in_persistent_and_strict(tmp_path):
    api = EngineAPI(tmp_path)
    try:
        assert api.bootstrap()["preferences"]["developer_mode"] is False
        with pytest.raises(ValueError):
            api.dispatch("preferences.save", {"developer_mode": "true"})
        api.dispatch(
            "preferences.save", {"developer_mode": True, "developer_acknowledged": True}
        )
    finally:
        api.close()
    api = EngineAPI(tmp_path)
    try:
        assert api.bootstrap()["preferences"]["developer_mode"] is True
    finally:
        api.close()


def test_report_excludes_profile_settings_and_keeps_logs_opt_in(tmp_path):
    api = EngineAPI(tmp_path)
    try:
        api.settings.update(nickname="PRIVATE-NAME", avatar="PRIVATE-IMAGE")
        diagnostics = Diagnostics()
        diagnostics.add("Not captured")
        report = diagnostics.snapshot(api, False)
        assert report["logs"]["rows"] == []
        assert report["metrics"]["rss_mb"] > 0
        assert "PRIVATE" not in str(report)
        diagnostics.set_enabled(True)
        for i in range(620):
            diagnostics.add(f"Event {i}")
        assert len(diagnostics.snapshot(api, True)["logs"]["rows"]) == 600
        diagnostics.set_enabled(False)
        assert diagnostics.read()["rows"] == []
    finally:
        api.close()
