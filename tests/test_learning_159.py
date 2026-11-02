import json
import sys
from pathlib import Path
from dataclasses import replace
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop"))
from engine_api import EngineAPI
from learning_calendar.models import Course
from learning_calendar.parsers import parse_assignments, submission_detail
from learning_calendar.attendance import project, save, read


def test_attendance_dates_and_mixed_classes():
    sources = {
        "lessons": [
            {
                "week_position": 1,
                "lessons": [
                    {
                        "lesson_position": 1,
                        "class_date": "2026-11-03",
                        "attendance_calc_type": "normal",
                    },
                    {
                        "lesson_position": 2,
                        "class_date": None,
                        "display_class_date": "온라인 강좌 2",
                    },
                ],
            }
        ],
        "lessons/attendances": [
            {
                "week_position": 1,
                "lesson_position": 1,
                "attendance_status": "attendance",
            },
            {"week_position": 1, "lesson_position": 2, "attendance_status": "late"},
        ],
        "attendance_items": {
            "attendance_items": [
                {
                    "item_id": 11,
                    "title": "영상",
                    "use_attendance": True,
                    "unlock_at": "2026-11-03T00:00:00Z",
                    "item_content_data": {"content_type": "movie"},
                }
            ]
        },
        "attendance_items/summary": {
            "attendance_summaries": {"11": {"attendance_status": "absent"}}
        },
    }
    rows = project(Course(1, "Course"), sources)
    assert len(rows) == 3
    assert rows[0]["date"] == "2026-11-03" and rows[0]["status"] == "attendance"
    assert rows[1]["date"] == "" and rows[1]["status"] == "late"
    assert rows[2]["status"] == "absent"
    assert project(Course(1, "C"), {}) == []


def test_attendance_partial_failure_preserves_previous(tmp_path):
    api = EngineAPI(tmp_path)
    sources = {
        "lessons": [
            {
                "week_position": 1,
                "lessons": [{"lesson_position": 1, "class_date": "2026-11-03"}],
            }
        ],
        "lessons/attendances": [
            {
                "week_position": 1,
                "lesson_position": 1,
                "attendance_status": "attendance",
            }
        ],
        "attendance_items": {"attendance_items": []},
        "attendance_items/summary": {"attendance_summaries": {}},
    }
    payload = {
        "responses": {
            f"/learningx/api/v1/courses/1/{k}": {"data": v} for k, v in sources.items()
        }
    }
    with api.store.db:
        save(api.store, [Course(1, "C")], payload)
    assert read(api.store)[0]["stale"] is False
    with api.store.db:
        save(api.store, [Course(1, "C")], {"responses": {}})
    assert read(api.store)[0]["status"] == "attendance" and read(api.store)[0]["stale"]
    with api.store.db:
        save(
            api.store,
            [Course(1, "C")],
            {"responses": {"/learningx/api/v1/courses/1/lessons": {"data": []}}},
        )
    assert read(api.store) == []
    api.close()


@pytest.mark.parametrize(
    "state,late,expected",
    [
        ("unsubmitted", False, "missing"),
        ("submitted", False, "submitted"),
        ("submitted", True, "late"),
        ("graded", True, "graded"),
        ("pending_review", False, "submitted"),
    ],
)
def test_submission_lifecycle_and_feedback(state, late, expected, tmp_path):
    sub = {
        "assignment_id": 3,
        "workflow_state": state,
        "late": late,
        "grade": "A",
        "submission_comments": [
            {
                "author_name": "Instructor",
                "comment": "Well written.",
                "created_at": "2026-11-03T00:00:00Z",
            }
        ],
    }
    events = parse_assignments(
        Course(1, "C"),
        [{"assignments": [{"id": 3, "name": "Task", "due_at": None}]}],
        [sub],
    )
    assert events[0].lms_data["status"] == expected
    assert bool(events[0].lms_data.get("comments")) == (state != "unsubmitted")
    api = EngineAPI(tmp_path)
    api.store.apply_batch([Course(1, "C")], {(1, "assignment"): events})
    assert api.store.events()[0].lms_data == events[0].lms_data
    changed = replace(events[0], lms_data={**events[0].lms_data, "grade": "B"})
    api.store.apply_batch([Course(1, "C")], {(1, "assignment"): [changed]})
    assert api.store.events()[0].lms_data["grade"] == "B"
    api.close()


def test_feedback_never_guesses_author_or_uses_unsubmitted_comments():
    assert "comments" not in submission_detail(
        {
            "workflow_state": "unsubmitted",
            "submission_comments": [{"comment": "secret"}],
        },
        False,
    )
    assert (
        submission_detail(
            {"workflow_state": "submitted", "submission_comments": "invalid"}, True
        )["comments"]
        == []
    )
    detail = submission_detail(
        {
            "workflow_state": "graded",
            "rubric_assessment": {"_1": {"comments": "Excellent argument."}},
        },
        True,
        [{"id": "_1", "description": "Content"}],
    )
    assert detail["rubric"] == [{"title": "Content", "text": "Excellent argument."}]
    malformed = submission_detail(
        {
            "workflow_state": "submitted",
            "submitted_at": "invalid",
            "submission_comments": [{"comment": "Feedback", "created_at": {}}],
        },
        True,
    )
    assert (
        malformed["submitted_at"] is None
        and malformed["comments"][0]["created_at"] is None
    )


def test_focus_pause_resume_breaks_and_free_mode(monkeypatch, tmp_path):
    import learning_calendar.focus as focus

    now = [100.0]
    monkeypatch.setattr(focus.time, "monotonic", lambda: now[0])
    api = EngineAPI(tmp_path)
    api.dispatch(
        "focus.command",
        {"action": "configure", "mode": "pomodoro", "work": 1, "short": 1, "long": 2},
    )
    api.dispatch("focus.command", {"action": "start"})
    now[0] += 40
    assert api.dispatch("focus.command", {"action": "pause"})["elapsed"] == 40
    now[0] += 60
    assert api.dispatch("focus.state", {})["elapsed"] == 40
    api.dispatch("focus.command", {"action": "start"})
    now[0] += 30
    assert api.dispatch("focus.state", {})["finished"]
    assert sum(r["seconds"] for r in api.dispatch("focus.totals", {})) == 60
    assert api.dispatch("focus.command", {"action": "next"})["phase"] == "break"
    api.dispatch("focus.command", {"action": "start"})
    now[0] += 60
    api.dispatch("focus.state", {})
    assert sum(r["seconds"] for r in api.dispatch("focus.totals", {})) == 60
    api.dispatch("focus.command", {"action": "reset"})
    api.dispatch(
        "focus.command",
        {"action": "configure", "mode": "free", "work": 25, "short": 5, "long": 15},
    )
    api.dispatch("focus.command", {"action": "start"})
    now[0] += 80
    assert api.dispatch("focus.command", {"action": "pause"})["elapsed"] == 80
    assert sum(r["seconds"] for r in api.dispatch("focus.totals", {})) == 140
    api.close()


def test_focus_database_reset_and_account_isolation(tmp_path, monkeypatch):
    import learning_calendar.focus as focus

    now = [100.0]
    monkeypatch.setattr(focus.time, "monotonic", lambda: now[0])
    api = EngineAPI(tmp_path)
    api.store.set_meta("canvas_user_id", "1")
    api.dispatch("focus.command", {"action": "start"})
    now[0] += 20
    api.activate_account("2")
    assert not api.dispatch("focus.state", {})["running"]
    assert api.dispatch("focus.totals", {}) == []
    api.dispatch("data.reset", {"confirmation": "초기화"})
    assert api.dispatch("focus.totals", {}) == []
    api.close()


def test_legacy_hotfix_versions_cannot_offer_a_downgrade():
    from learning_calendar.updates import version_key

    assert version_key("1.5.8") < version_key("1.5.81") < version_key("1.5.9")
    assert version_key("1.4.2") < version_key("1.4.21") < version_key("1.5.9")


def test_browser_feedback_is_not_skipped_for_already_graded_assignments():
    import threading
    from engine_webview import BrowserClient

    responses = {
        "/api/v1/courses/1/assignments": {
            "data": [
                {"id": 3, "name": "Task", "submission": {"workflow_state": "graded"}}
            ]
        },
        "/api/v1/courses/1/students/submissions": {
            "data": [
                {
                    "assignment_id": 3,
                    "workflow_state": "graded",
                    "late": True,
                    "submission_comments": [
                        {"author_name": "Instructor", "comment": "Well written"}
                    ],
                }
            ]
        },
    }
    client = BrowserClient({"responses": responses}, threading.Event())
    try:
        event = client._course_assignments(Course(1, "C"))[0]
        assert (
            event.lms_data["late"]
            and event.lms_data["comments"][0]["text"] == "Well written"
        )
        responses["/api/v1/courses/1/students/submissions"] = {"error": "HTTP_503"}
        event = client._course_assignments(Course(1, "C"))[0]
        assert event.completed and event.lms_data["feedback_available"] is False
    finally:
        client.session.close()


def test_focus_suspend_does_not_inflate_learning_time(tmp_path, monkeypatch):
    import learning_calendar.focus as focus

    now = [100.0]
    monkeypatch.setattr(focus.time, "monotonic", lambda: now[0])
    api = EngineAPI(tmp_path)
    api.dispatch("focus.command", {"action": "start"})
    now[0] += 3600
    assert not api.dispatch("focus.state", {})["running"]
    assert api.dispatch("focus.totals", {}) == []
    api.close()


def test_focus_records_survive_personal_backup(tmp_path, monkeypatch):
    import learning_calendar.focus as focus
    from learning_calendar.local_backup import write_backup, read_backup, restore_backup

    now = [100.0]
    monkeypatch.setattr(focus.time, "monotonic", lambda: now[0])
    api = EngineAPI(tmp_path / "first")
    api.dispatch("focus.command", {"action": "start"})
    now[0] += 30
    api.dispatch("focus.command", {"action": "pause"})
    backup = tmp_path / "data.calix"
    write_backup(backup, api.store, api.folder)
    value = read_backup(backup)
    other = EngineAPI(tmp_path / "second")
    restore_backup(value, other.store, other.folder)
    assert sum(row["seconds"] for row in other.dispatch("focus.totals", {})) == 30
    api.close()
    other.close()
