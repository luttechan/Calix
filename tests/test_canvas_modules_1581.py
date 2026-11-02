import sys
from pathlib import Path
from copy import deepcopy
import pytest
from learning_calendar.canvas_modules import parse_canvas_modules
from learning_calendar.models import Course, Event
from learning_calendar.storage import Store

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop"))
from engine_webview import BrowserSyncTask


def content(complete=True):
    return dict(
        complete=complete,
        items=[
            dict(
                id=31,
                source_id=33,
                source_kind="file",
                title="모듈 영상",
                url="/courses/2/modules/items/31",
                week="1주차",
                completed=True,
                content_details=dict(due_at="2026-11-05T23:59:00+09:00"),
            )
        ],
    )


def packet(canvas):
    return dict(
        owner="7",
        transport="webview2",
        courses=[dict(id=2, name="수업")],
        results=[
            dict(
                course_id=2,
                canvas=canvas,
                sources_complete=canvas["complete"],
                verified=True,
            )
        ],
        responses={
            "/api/v1/courses/2/assignments": dict(
                data=[
                    dict(
                        id=4,
                        name="과제",
                        due_at="2026-11-07T00:00:00Z",
                        submission_types=["online_upload"],
                        submission=dict(workflow_state="unsubmitted"),
                    )
                ]
            )
        },
    )


def run(value, path):
    task = BrowserSyncTask(value, path)
    success = []
    errors = []
    task.success.connect(success.append)
    task.error.connect(errors.append)
    task.run()
    assert not errors, errors
    return success[0]


def test_canvas_only_course_does_not_require_a_learningx_snapshot(tmp_path):
    path = tmp_path / "learning.db"
    result = run(packet(content()), path)
    assert not result["warnings"]
    store = Store(path)
    try:
        video = next(e for e in store.events() if e.kind == "movie")
        assert (
            video.key == "movie:2:canvas-file:33"
            and video.completed
            and video.completion_verified
        )
        assert video.week == "1주차" and video.due_at.startswith("2026-11-05")
    finally:
        store.close()


def test_timeout_never_archives_existing_videos_and_assignments_still_update(tmp_path):
    path = tmp_path / "learning.db"
    run(packet(content()), path)
    row = dict(complete=False, items=[], warnings=["모듈 응답 시간 초과"])
    result = run(packet(row), path)
    assert result["warnings"]
    store = Store(path)
    try:
        assert len([e for e in store.events() if e.kind == "movie"]) == 1
    finally:
        store.close()


def test_confirmed_empty_module_course_is_normal(tmp_path):
    result = run(packet(dict(complete=True, items=[])), tmp_path / "learning.db")
    assert (
        not result["warnings"]
        and result["course_checks"][2]["video_state"] == "complete"
    )


def test_repeated_file_across_modules_is_one_video_and_unknown_completion_is_not_guessed():
    value = content()
    row = deepcopy(value["items"][0])
    row.update(id=32, url="/courses/2/modules/items/32")
    value["items"].append(row)
    events = parse_canvas_modules(Course(2, "수업"), value)
    assert len(events) == 1 and events.complete
    value = content()
    value["items"][0]["completed"] = None
    assert not parse_canvas_modules(Course(2, "수업"), value)[0].completion_verified


@pytest.mark.parametrize(
    "field,value",
    [
        ("url", "https://evil.invalid/courses/2/modules/items/31"),
        ("url", "/courses/3/modules/items/31"),
        ("id", True),
        ("source_id", 0),
        ("content_details", dict(due_at="tomorrow")),
    ],
)
def test_invalid_module_data_never_authorizes_destructive_replacement(field, value):
    data = content()
    data["items"][0][field] = value
    result = parse_canvas_modules(Course(2, "수업"), data)
    assert not result.complete and len(result) == 0


def test_partial_assignment_list_from_modules_preserves_missing_assignments(tmp_path):
    path = tmp_path / "learning.db"
    data = packet(content())
    run(data, path)
    data["responses"]["/api/v1/courses/2/assignments"] = dict(
        data=[
            dict(
                id=5,
                name="추가 과제",
                submission_types=["online_upload"],
                submission=dict(workflow_state="unsubmitted"),
            )
        ],
        complete=False,
    )
    result = run(data, path)
    assert result["warnings"]
    store = Store(path)
    try:
        assert len([e for e in store.events() if e.kind == "assignment"]) == 2
    finally:
        store.close()
