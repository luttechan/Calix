import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop"))
from engine_api import EngineAPI

PASSWORD = "Calix grade prerequisite phrase!"
POLICY = dict(main=False, timetable=False, grades=False, idle_minutes=5)


@pytest.mark.parametrize("method,params", [
    ("grades.read", {}),
    ("grades.save", dict(title="Private course", credits=3, grade="A+")),
    ("grades.scale", dict(scale="4.3")),
    ("grades.delete", dict(id="manual:unknown")),
])
def test_grade_requests_require_a_configured_password(tmp_path, method, params):
    api = EngineAPI(tmp_path)
    try:
        with pytest.raises(ValueError, match="비밀번호를 설정"):
            api.dispatch(method, params)
        assert isinstance(api.dispatch("bootstrap", {})["sessions"], list)
    finally:
        api.close()


def test_password_prerequisite_preserves_optional_section_lock(tmp_path):
    api = EngineAPI(tmp_path)
    api.dispatch("security.setup", dict(password=PASSWORD, policy=POLICY))
    api.dispatch("grades.save", dict(title="Saved course", credits=3, grade="A+"))
    assert api.dispatch("grades.read", {})["summary"]["gpa"] == "4.50"
    api.close()
    api = EngineAPI(tmp_path)
    try:
        with pytest.raises(ValueError, match="잠금을 해제"):
            api.dispatch("grades.read", {})
        api.dispatch("security.unlock", dict(password=PASSWORD))
        assert api.dispatch("grades.read", {})["summary"]["gpa"] == "4.50"
    finally:
        api.close()
