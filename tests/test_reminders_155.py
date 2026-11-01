from datetime import datetime, timedelta
from pathlib import Path
import json
import sys
import pytest
from learning_calendar.models import Course, Event, KST
from learning_calendar.reminders import DEFAULTS, validate, pending, check

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop"))
from engine_api import EngineAPI

NOW = datetime(2026, 11, 2, 12, tzinfo=KST)


def event(key, minutes, kind="assignment", completed=False):
    return Event(
        key,
        1,
        "수업",
        kind,
        key,
        (NOW + timedelta(minutes=minutes)).isoformat(),
        completed,
    )


@pytest.fixture
def api(tmp_path):
    value = EngineAPI(tmp_path)
    value.settings.update(onboarding_complete=True, reminders=DEFAULTS.copy())
    yield value
    value.close()


def save(api, events):
    api.store.apply_batch(
        [Course(1, "수업")],
        {(1, k): [e for e in events if e.kind == k] for k in ("assignment", "movie")},
    )


def test_due_boundaries_skip_done_overdue_and_unsupported_types():
    events = [
        event("past", -1),
        event("now", 0),
        event("edge", 60),
        event("general", 61, "movie"),
        event("later", 1441),
        event("done", 10, completed=True),
        event("task", 10, "task"),
    ]
    rows = pending(events, DEFAULTS, NOW)
    assert [(e.key, stage) for e, stage, _ in rows] == [
        ("edge", "urgent"),
        ("general", "general"),
    ]


def test_custom_minutes_days_and_independent_event_types():
    settings = validate(dict(urgent_minutes=17, general_days=3, assignments=False))
    rows = pending(
        [
            event("assignment", 1),
            event("video", 17, "movie"),
            event("day3", 4320, "movie"),
            event("day4", 4321, "movie"),
        ],
        settings,
        NOW,
    )
    assert [(e.key, stage) for e, stage, _ in rows] == [
        ("video", "urgent"),
        ("day3", "general"),
    ]


def test_today_option_uses_local_date():
    settings = validate(dict(urgent=False, general_days=0))
    assert [
        e.key
        for e, _, _ in pending(
            [event("today", 700), event("tomorrow", 721)], settings, NOW
        )
    ] == ["today"]


def test_timer_deduplicates_but_explicit_sync_repeats(api):
    save(api, [event("video", 50, "movie"), event("assignment", 70)])
    first = check(api, "startup", NOW)
    assert first["urgent"] and first["sound"] == "crit" and first["total"] == 2
    assert {e["kind"] for e in first["events"]} == {"assignment", "movie"}
    assert check(api, "timer", NOW) is None
    assert check(api, "sync", NOW)["total"] == 2


def test_general_escalates_once_to_critical(api):
    save(api, [event("video", 61, "movie")])
    assert check(api, "startup", NOW)["sound"] == "1"
    assert check(api, "timer", NOW + timedelta(minutes=1))["sound"] == "crit"
    assert check(api, "timer", NOW + timedelta(minutes=2)) is None


def test_startup_disabled_seeds_existing_thresholds_without_showing(api):
    save(api, [event("task", 61)])
    api.settings["reminders"].update(startup=False, sync=False)
    assert check(api, "startup", NOW) is None
    assert check(api, "timer", NOW) is None
    assert check(api, "sync", NOW) is None
    assert check(api, "timer", NOW + timedelta(minutes=1))["urgent"]


def test_disabled_and_sound_off(api):
    save(api, [event("video", 10, "movie")])
    api.settings["reminders"]["enabled"] = False
    assert check(api, "startup", NOW) is None
    api.settings["reminders"].update(enabled=True, sound=False)
    assert check(api, "startup", NOW)["sound"] == ""


def test_settings_persist_and_reject_invalid_partial_updates(tmp_path):
    api = EngineAPI(tmp_path)
    chosen = validate(
        dict(
            startup=False,
            sync=True,
            urgent_minutes=37,
            general_days=5,
            track="10",
            volume=0.3,
        )
    )
    api.dispatch("reminders.save", chosen)
    api.close()
    api = EngineAPI(tmp_path)
    assert api.bootstrap()["preferences"]["reminders"] == chosen
    for bad in [
        dict(urgent_minutes=0),
        dict(general_days=True),
        dict(volume=float("nan")),
        dict(track="../x"),
        dict(enabled=1),
    ]:
        with pytest.raises(ValueError):
            api.dispatch("reminders.save", bad)
    assert api.bootstrap()["preferences"]["reminders"] == chosen
    api.close()


def test_ledger_survives_restart_and_new_deadline_is_not_lost(tmp_path):
    api = EngineAPI(tmp_path)
    api.settings.update(onboarding_complete=True, reminders=DEFAULTS.copy())
    save(api, [event("video", 90, "movie")])
    assert check(api, "timer", NOW)
    api.close()
    api = EngineAPI(tmp_path)
    api.settings.update(onboarding_complete=True, reminders=DEFAULTS.copy())
    assert check(api, "timer", NOW) is None
    save(api, [event("video", 91, "movie")])
    assert check(api, "timer", NOW)
    api.close()


def test_payload_and_history_are_bounded(api):
    save(api, [event(f"video{i}", 30, "movie") for i in range(120)])
    payload = check(api, "startup", NOW)
    assert payload["total"] == 120 and len(payload["events"]) == 50
    history = {f"old{i}": NOW.timestamp() - 20 * 86400 for i in range(2500)}
    api.store.set_meta("reminder_history", json.dumps(history))
    check(api, "startup", NOW)
    assert len(json.loads(api.store.get_meta("reminder_history"))) <= 2000


def test_all_alarm_tracks_and_ui_browser_settings_are_packaged():
    root = Path(__file__).resolve().parents[1]
    for name in [*[f"{i}.mp3" for i in range(1, 11)], "crit.mp3"]:
        assert (root / "asset/alarm" / name).stat().st_size > 1000
    config = json.loads(
        (root / "desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8")
    )
    args = config["app"]["windows"][0]["additionalBrowserArgs"]
    assert "--autoplay-policy=no-user-gesture-required" in args
    assert args in (root / "desktop/src-tauri/src/reminder.rs").read_text(
        encoding="utf-8"
    )
    assert "additional_browser_args(crate::reminder::UI_ARGS)" in (
        root / "desktop/src-tauri/src/auth.rs"
    ).read_text(encoding="utf-8")
