from copy import deepcopy
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop"))
from engine_webview import BrowserSyncTask
from learning_calendar.storage import Store
from learning_calendar.models import Course, Event


@pytest.fixture
def payload():
    return dict(
        transport="webview2",
        owner="7",
        courses=[dict(id=2, name="수업")],
        results=[
            dict(
                course_id=2,
                verified=True,
                empty_confirmed=False,
                snapshot=dict(
                    state="ready",
                    owner="7",
                    course_id="2",
                    name="수업",
                    term="2026년 2학기",
                    weeks=1,
                    expected=1,
                    items=[
                        dict(
                            kind="movie",
                            title="영상",
                            url="/courses/2/modules/items/12",
                            start="",
                            due="11월 5일 오후 11:59",
                            lock="",
                            week="1주차",
                            completed=True,
                            attendance="attendance",
                        )
                    ],
                ),
            )
        ],
        responses={
            "/api/v1/courses/2/assignments": dict(
                data=[
                    dict(
                        id=4,
                        name="과제",
                        due_at="2026-11-06T23:59:00+09:00",
                        submission_types=["online_upload"],
                        submission=dict(workflow_state="unsubmitted"),
                    )
                ]
            )
        },
    )


def test_browser_transport_does_not_make_http_requests(payload, tmp_path, monkeypatch):
    import requests

    monkeypatch.setattr(
        requests.Session,
        "send",
        lambda *a, **k: pytest.fail("Cookie transfer/HTTP request attempted"),
    )
    task = BrowserSyncTask(payload, tmp_path / "learning.db")
    owner, courses, batches, warnings, auth, checks = task._fetch_network()
    assert owner == "7" and len(courses) == 1 and not warnings and not auth
    assert len(batches[(2, "movie")]) == 1 and len(batches[(2, "assignment")]) == 1
    assert batches[(2, "movie")][0].completed


def test_local_notes_survive_native_browser_sync(payload, tmp_path):
    path = tmp_path / "learning.db"
    store = Store(path)
    event = Event("movie:2:12", 2, "수업", "movie", "이전 영상", None, False)
    store.apply_batch([Course(2, "수업")], {(2, "movie"): [event]})
    store.set_note(event.key, "보존할 메모")
    store.close()
    task = BrowserSyncTask(payload, path)
    errors = []
    task.error.connect(errors.append)
    task.run()
    assert not errors
    store = Store(path)
    try:
        assert (
            next(e for e in store.events() if e.key == event.key).note == "보존할 메모"
        )
    finally:
        store.close()


@pytest.mark.parametrize(
    "change", ["unverified", "unconfirmed-empty", "other-owner", "missing"]
)
def test_unverified_video_results_keep_existing_videos(payload, tmp_path, change):
    if change == "unverified":
        payload["results"][0]["verified"] = False
    if change == "unconfirmed-empty":
        payload["results"][0]["snapshot"]["items"] = []
    if change == "other-owner":
        payload["results"][0]["snapshot"]["owner"] = "8"
    if change == "missing":
        payload["results"] = []
    task = BrowserSyncTask(payload, tmp_path / "learning.db")
    _, _, batches, warnings, _, _ = task._fetch_network()
    assert (2, "movie") not in batches and warnings
    assert (2, "assignment") in batches


def test_confirmed_empty_list_can_replace_old_videos(payload, tmp_path):
    payload["results"][0]["snapshot"]["items"] = []
    payload["results"][0]["empty_confirmed"] = True
    task = BrowserSyncTask(payload, tmp_path / "learning.db")
    _, _, batches, warnings, _, _ = task._fetch_network()
    assert batches[(2, "movie")] == [] and not warnings


def test_snapshot_script_matches_existing_extraction_rules():
    from learning_calendar.dom_videos import SNAPSHOT_SCRIPT

    assert (ROOT / "desktop/scripts/campus-snapshot.js").read_text(
        encoding="utf-8"
    ) == SNAPSHOT_SCRIPT


def test_remote_school_webviews_have_no_application_permissions():
    import json

    for path in (ROOT / "desktop/src-tauri/capabilities").glob("*.json"):
        value = json.loads(path.read_text(encoding="utf-8"))
        assert not value.get("remote")
        assert not {"campus-worker", "school-login"} & set(
            value.get("windows", []) + value.get("webviews", [])
        )
