import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop"))
from engine_api import EngineAPI


def test_manual_lock_works_with_idle_lock_disabled_and_clears_section_access(tmp_path):
    api = EngineAPI(tmp_path)
    password = "Calix manual lock phrase!"
    try:
        api.dispatch("security.setup", dict(password=password, policy=dict(main=False, timetable=True, grades=True, idle_minutes=5)))
        api.dispatch("security.unlock", dict(password=password, scope="grades"))
        api.dispatch("security.unlock", dict(password=password, scope="timetable"))
        api.dispatch("grades.save", dict(title="Saved subject", credits=3, grade="A+"))
        locked = api.dispatch("security.lock", dict(scope="main"))
        assert locked["locked"] and not locked["policy"]["main"] and locked["unlocked"] == []
        snapshot = api.dispatch("bootstrap", {})
        assert snapshot["events"] == snapshot["sessions"] == snapshot["courses"] == []
        for method in ("grades.read", "focus.state"):
            with pytest.raises(ValueError, match="잠금을 해제"):
                api.dispatch(method, {})
        with pytest.raises(ValueError):
            api.dispatch("security.unlock", dict(password="wrong password"))
        api.dispatch("security.unlock", dict(password=password))
        with pytest.raises(ValueError, match="잠금을 해제"):
            api.dispatch("grades.read", {})
        api.dispatch("security.unlock", dict(password=password, scope="grades"))
        assert api.dispatch("grades.read", {})["summary"]["gpa"] == "4.50"
    finally:
        api.close()
