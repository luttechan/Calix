import json
import sqlite3
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop"))
from engine_api import EngineAPI
from learning_calendar.grades import summary
from learning_calendar.local_backup import read_backup, write_backup

PASSWORD = "Calix test phrase 160!"
POLICY = dict(main=True, timetable=True, grades=True, idle_minutes=1)


def test_grade_weighting_and_pass_fail():
    items = [
        dict(credits=3, grade="A+", excluded=0),
        dict(credits=2, grade="B", excluded=0),
        dict(credits=2, grade="P", excluded=0),
        dict(credits=3, grade="NP", excluded=0),
        dict(credits=3, grade="F", excluded=1),
    ]
    assert summary(items, "4.5") == dict(gpa="3.90", graded_credits=5, earned_credits=7, registered_credits=10, pending=0)
    assert summary(items, "4.3")["gpa"] == "3.78"
    assert summary(items, "4.0")["gpa"] == "3.60"
    assert summary([dict(credits=3, grade="P", excluded=0)], "4.5")["gpa"] is None


def test_encryption_restart_scopes_backup_and_idle(tmp_path):
    api = EngineAPI(tmp_path)
    term = api.bootstrap()["mainTerm"]
    api.dispatch("grades.save", dict(semester=term, title="Private course", credits=3, grade="A+", excluded=False))
    before = api.dispatch("grades.read", {"semester": term})
    assert before["summary"]["gpa"] == "4.50"
    api.dispatch("security.setup", dict(password=PASSWORD, policy=POLICY))
    assert not (tmp_path / "learning.db").read_bytes().startswith(b"SQLite format 3")
    assert b"Private course" not in (tmp_path / "learning.db").read_bytes()
    with sqlite3.connect(tmp_path / "learning.db") as raw:
        with pytest.raises(sqlite3.DatabaseError):
            raw.execute("SELECT * FROM courses").fetchall()
    with pytest.raises(ValueError):
        api.dispatch("grades.read", {"semester": term})
    api.dispatch("security.unlock", dict(password=PASSWORD, scope="grades"))
    assert api.dispatch("grades.read", {"semester": term})["summary"]["gpa"] == "4.50"
    api.close()

    api = EngineAPI(tmp_path)
    assert api.bootstrap()["security"]["locked"]
    assert not api.bootstrap()["events"] and not api.bootstrap()["sessions"]
    with pytest.raises(ValueError):
        api.dispatch("security.unlock", dict(password="incorrect", scope="main"))
    api.dispatch("security.unlock", dict(password=PASSWORD, scope="main"))
    with pytest.raises(ValueError):
        api.dispatch("grades.read", {"semester": term})
    api.dispatch("security.unlock", dict(password=PASSWORD, scope="grades"))
    api.dispatch("security.unlock", dict(password=PASSWORD, scope="timetable"))
    backup = tmp_path / "test.calix"
    write_backup(backup, api.store, tmp_path)
    assert not backup.read_bytes().startswith(b"PK")
    assert read_backup(backup, password=PASSWORD)["grades"][0]["title"] == "Private course"
    with pytest.raises(ValueError):
        read_backup(backup, password="bad")
    api.dispatch("grades.save", dict(semester=term, title="Temporary", credits=2, grade="F"))
    api.dispatch("backup.restore", dict(path=str(backup.resolve()), password=PASSWORD))
    assert len(api.dispatch("grades.read", {"semester": term})["items"]) == 1
    api.security.activity = time.monotonic() - 61
    assert api.bootstrap()["security"]["locked"]
    assert not api.bootstrap()["events"]
    api.close()


def test_initialization_can_resume_after_migration_failure(tmp_path, monkeypatch):
    from learning_calendar import secure_db
    api = EngineAPI(tmp_path)
    api.dispatch("grades.save", dict(title="Preserve after failure", credits=3, grade="A"))
    original = secure_db.encrypt_database
    called = False

    def fail_once(path, key):
        nonlocal called
        if not called:
            called = True
            raise OSError("Injected interruption")
        return original(path, key)

    monkeypatch.setattr(secure_db, "encrypt_database", fail_once)
    with pytest.raises(OSError):
        api.dispatch("security.setup", dict(password=PASSWORD, policy=POLICY))
    api.close()
    assert json.loads((tmp_path / "app-lock.json").read_text())["header"]
    api = EngineAPI(tmp_path)
    api.dispatch("security.unlock", dict(password=PASSWORD, scope="grades"))
    assert api.dispatch("grades.read", {})["items"][0]["title"] == "Preserve after failure"
    api.close()


def test_password_change_and_locked_configuration(tmp_path):
    api = EngineAPI(tmp_path)
    api.dispatch("grades.save", dict(title="Saved grade", credits=2, grade="B+"))
    api.dispatch("security.setup", dict(password=PASSWORD, policy=POLICY))
    replacement = "Replacement phrase 160!"
    api.dispatch("security.configure", dict(password=PASSWORD, replacement=replacement, policy=POLICY))
    api.dispatch("security.lock", {"scope": "main"})
    with pytest.raises(ValueError):
        api.dispatch("security.configure", dict(password=replacement, policy=dict(POLICY, grades=False)))
    api.close()
    api = EngineAPI(tmp_path)
    with pytest.raises(ValueError):
        api.dispatch("security.unlock", dict(password=PASSWORD))
    api.dispatch("security.unlock", dict(password=replacement, scope="grades"))
    assert api.dispatch("grades.read", {})["items"][0]["title"] == "Saved grade"
    api.close()
