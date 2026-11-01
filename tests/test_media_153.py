import json
from pathlib import Path
import pytest
from learning_calendar.media_types import VIDEO_KINDS
from learning_calendar.dom_videos import parse_screen
from learning_calendar.models import Course

SITE_VIDEO_TYPES = {
    "movie",
    "ssz",
    "syncthink",
    "estage",
    "xenoglobal",
    "oncast",
    "screenlecture",
    "lecturecam",
    "readystream",
    "webstudio",
    "everlec",
    "movie360",
    "mp4",
    "zoom",
    "audio",
    "youtube",
    "remix",
    "metaverse_conference",
    "video_conference",
    "external_youtube",
    "external_video",
}


def screen(kind):
    return dict(
        state="ready",
        course_id="2",
        owner="7",
        term="2026년 2학기",
        weeks=15,
        expected=15,
        unsupported_items=0,
        items=[
            dict(
                kind=kind,
                title="학습자료",
                url="/courses/2/modules/items/11",
                week="2주차",
                completed=True,
                attendance="attendance",
                start="9월 1일 오전 9:00",
                due="12월 8일 오전 9:00",
                lock="",
            )
        ],
    )


def test_shared_rules_cover_school_player_classification():
    assert SITE_VIDEO_TYPES <= VIDEO_KINDS


@pytest.mark.parametrize("kind", sorted(SITE_VIDEO_TYPES))
def test_all_school_video_types_keep_the_existing_event_identity(kind):
    events = parse_screen(Course(2, "수업"), screen(kind))
    assert events.complete and len(events) == 1
    assert events[0].key == "movie:2:11" and events[0].kind == "movie"
    assert events[0].completed and events[0].completion_verified


def test_unknown_learning_content_cannot_authorize_empty_replacement():
    value = screen("movie")
    value["items"] = []
    value["unsupported_items"] = 1
    with pytest.raises(ValueError, match="기존 영상을 유지"):
        parse_screen(Course(2, "수업"), value)


def test_shared_rules_are_included_in_native_and_python_bundles():
    root = Path(__file__).resolve().parents[1]
    assert "learning_calendar/media_types.json" in (root / "Calix.spec").read_text(
        encoding="utf-8"
    )
    assert "../../../learning_calendar/media_types.json" in (
        root / "desktop/src-tauri/src/campus.rs"
    ).read_text(encoding="utf-8")
