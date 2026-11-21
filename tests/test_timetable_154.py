import json
import sqlite3
import sys
from pathlib import Path
import pytest
from learning_calendar.storage import Store
from learning_calendar.models import Course
from learning_calendar.local_backup import write_backup, read_backup, restore_backup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop"))
from engine_api import EngineAPI


def test_previous_version_requires_semester_confirmation_and_keeps_data(tmp_path):
    db = sqlite3.connect(tmp_path / "learning.db")
    db.execute(
        "CREATE TABLE timetable(id INTEGER PRIMARY KEY,course_id INTEGER,day INTEGER,start_time TEXT,end_time TEXT,professor TEXT,room TEXT)"
    )
    db.execute("INSERT INTO timetable VALUES(7,1,0,'09:00','10:00','교수','A101')")
    db.commit()
    db.close()
    api = EngineAPI(tmp_path)
    try:
        assert not api.bootstrap()["timetableConfigured"]
        api.dispatch("timetable.term.configure", {"year": 2025, "term": 1})
        data = api.bootstrap()
        assert data["timetableConfigured"] and data["mainTerm"] == "2025학년도 1학기"
        assert len(data["sessions"]) == 1 and data["sessions"][0]["id"] == 7
        assert data["sessions"][0]["semester"] == data["mainTerm"]
        with pytest.raises(ValueError):
            api.dispatch("timetable.term.configure", {"year": 2026, "term": 2})
    finally:
        api.close()
    reopened = EngineAPI(tmp_path)
    assert reopened.bootstrap()["timetableConfigured"]
    reopened.close()


def test_multiple_slots_are_atomic_including_updates(tmp_path):
    api = EngineAPI(tmp_path)
    shared = dict(
        course_id=0,
        title="스터디",
        slots=[
            dict(day=0, start_time="09:00", end_time="10:00"),
            dict(day=2, start_time="11:00", end_time="12:00"),
        ],
    )
    try:
        ids = api.dispatch("timetable.save", shared)
        assert len(ids) == 2 and len(api.store.timetable()) == 2
        before = api.store.timetable()
        with pytest.raises(ValueError):
            api.dispatch(
                "timetable.save",
                {
                    **shared,
                    "id": ids[0],
                    "title": "수정",
                    "slots": [
                        dict(day=1, start_time="09:00", end_time="10:00"),
                        dict(day=2, start_time="11:30", end_time="12:30"),
                    ],
                },
            )
        assert api.store.timetable() == before
        with pytest.raises(ValueError):
            api.dispatch(
                "timetable.save",
                {
                    **shared,
                    "slots": [
                        dict(day=3, start_time="09:00", end_time="10:00"),
                        dict(day=3, start_time="09:30", end_time="10:30"),
                    ],
                },
            )
        assert api.store.timetable() == before
    finally:
        api.close()


def test_semester_isolates_conflicts_off_days_and_main_default(tmp_path):
    api = EngineAPI(tmp_path)
    try:
        api.dispatch("timetable.term.configure", dict(year=2026, term=2))
        first = api.bootstrap()["mainTerm"]
        second = api.dispatch("timetable.term.add", dict(year=2027, term=1))
        for term in (first, second):
            api.dispatch(
                "timetable.save",
                dict(
                    course_id=0,
                    title=term,
                    semester=term,
                    day=0,
                    start_time="09:00",
                    end_time="10:00",
                ),
            )
        api.dispatch("timetable.off", dict(semester=first, days=[2]))
        api.dispatch("timetable.off", dict(semester=second, days=[4]))
        api.dispatch("timetable.term.main", dict(name=second))
        assert len(api.bootstrap()["sessions"]) == 2
        assert api.bootstrap()["offDays"] == [4]
        assert [s["title"] for s in api.store.timetable()] == [second]
        with pytest.raises(ValueError):
            api.dispatch("timetable.term.add", dict(year=2027, term=1))
        with pytest.raises(ValueError):
            api.dispatch("timetable.term.main", dict(name="없음"))
    finally:
        api.close()


def test_all_semesters_survive_backup_and_restore(tmp_path):
    api = EngineAPI(tmp_path)
    try:
        api.dispatch("timetable.term.configure", dict(year=2026, term=2))
        second = api.dispatch("timetable.term.add", dict(year=2027, term=1))
        for term in (api.bootstrap()["mainTerm"], second):
            api.dispatch(
                "timetable.save",
                dict(
                    course_id=0,
                    title="수업",
                    semester=term,
                    day=0,
                    start_time="09:00",
                    end_time="10:00",
                ),
            )
        api.dispatch("timetable.term.main", dict(name=second))
        api.dispatch("timetable.off", dict(semester=second, days=[3]))
        before = api.bootstrap()
        archive = tmp_path / "backup.calix"
        write_backup(archive, api.store, tmp_path)
        value = read_backup(archive)
        restore_backup(value, api.store, tmp_path)
        after = api.bootstrap()
        assert (
            after["timetableTerms"] == before["timetableTerms"]
            and after["mainTerm"] == second
        )
        assert (
            len(after["sessions"]) == 2
            and after["offDays"] == [3]
            and after["timetableConfigured"]
        )
    finally:
        api.close()


@pytest.mark.parametrize("year,term", [(0, 1), (2026, 3), (2026, True), (2026.5, 1)])
def test_invalid_semesters_do_not_change_existing_data(tmp_path, year, term):
    api = EngineAPI(tmp_path)
    before = api.store.timetable_config()
    with pytest.raises(ValueError):
        api.dispatch("timetable.term.add", dict(year=year, term=term))
    assert api.store.timetable_config() == before
    api.close()


@pytest.mark.parametrize("term", ["여름", "겨울"])
def test_seasonal_semesters_can_be_created_and_selected(tmp_path, term):
    api = EngineAPI(tmp_path)
    api.dispatch("timetable.term.configure", dict(year=2026, term=2))
    name = api.dispatch("timetable.term.add", dict(year=2027, term=term))
    assert name == f"2027학년도 {term} 계절학기"
    api.dispatch("timetable.term.main", dict(name=name))
    assert api.bootstrap()["mainTerm"] == name
    api.close()


def test_legacy_auto_term_preferences_are_removed_and_only_manual_selection_changes_main(tmp_path):
    api = EngineAPI(tmp_path)
    try:
        autumn = api.dispatch("semester.configure", dict(year=2026, term=2))
        spring = api.dispatch("semester.add", dict(year=2027, term=1))
        config = api.store.timetable_config()
        config.update(automatic=True, seasonal=True)
        config["terms"][1].update(startsOn="1900-01-01", endsOn="2200-12-31")
        api.store.set_meta("timetable_config", json.dumps(config))
        api.store.db.execute("INSERT INTO courses(id,name) VALUES(1,'이전 과목')")
        api.store.db.commit()
        assert api.bootstrap()["mainTerm"] == autumn
        assert all("startsOn" not in term for term in api.bootstrap()["timetableTerms"])
        api.dispatch("semester.main", dict(name=spring))
        assert api.dispatch("semester.roster", {}) == {autumn: [1]}
        api.store.apply_batch([Course(1, "이전 과목"), Course(2, "새 과목")], {(2, "assignment"): []}, grade_semester=spring)
        assert api.dispatch("semester.roster", {}) == {autumn: [1], spring: [2]}
        assert api.bootstrap()["mainTerm"] == spring
        assert "automatic" not in json.loads(api.store.get_meta("timetable_config"))
    finally:
        api.close()


def test_course_transfer_preserves_saved_grades_and_is_atomic(tmp_path):
    api = EngineAPI(tmp_path)
    try:
        first = api.dispatch("semester.configure", dict(year=2026, term=1))
        second = api.dispatch("semester.add", dict(year=2026, term=2))
        assert api.bootstrap()["mainTerm"] == first
        api.dispatch("semester.main", dict(name=second))
        assert api.bootstrap()["mainTerm"] == second
        api.store.apply_batch([Course(1, "수업 A"), Course(2, "수업 B")], {(1, "assignment"): []}, grade_semester=first)
        api.store.db.execute("INSERT INTO grade_items(semester,id,title) VALUES(?,?,?)", (first, "course:1", "수업 A"))
        api.store.db.commit()
        with pytest.raises(ValueError, match="학점 기록"):
            api.dispatch("semester.move", dict(source=first, target=second, course_ids=[1, 2]))
        assert api.dispatch("semester.roster", {}) == {first: [1, 2]}
        assert api.dispatch("semester.move", dict(source=first, target=second, course_ids=[2])) == 1
        api.store.apply_batch([Course(2, "수업 B")], {(2, "assignment"): []}, grade_semester=first)
        assert api.dispatch("semester.roster", {}) == {first: [1], second: [2]}
    finally:
        api.close()
