"""Exercise the actual service class with offline collaborators."""

import ast
import json
import logging
import sys
import secrets
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, Signal, QTimer, QProcess, QProcessEnvironment

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop"))
from engine_diagnostics import Diagnostics


@pytest.fixture
def service(tmp_path):
    tree = ast.parse((ROOT / "desktop/engine_runtime.py").read_text(encoding="utf-8"))
    definition = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "Service"
    )
    output = []
    from engine_api import EngineAPI

    api = EngineAPI(tmp_path)
    namespace = dict(
        api=api,
        QObject=QObject,
        Signal=Signal,
        QTimer=QTimer,
        QProcess=QProcess,
        QProcessEnvironment=QProcessEnvironment,
        diagnostics=Diagnostics(),
        json=json,
        logging=logging,
        sys=sys,
        ROOT=ROOT,
        folder=tmp_path,
        emit=output.append,
        secrets=secrets,
        threading=threading,
    )
    exec(
        compile(
            ast.Module(body=[definition], type_ignores=[]), "engine_runtime.py", "exec"
        ),
        namespace,
    )
    instance = namespace["Service"]()
    yield instance, output
    api.close()


def test_anki_is_opt_in_and_discards_requests_after_disabling(service, monkeypatch):
    instance, output = service
    waiting = []

    class Worker:
        def __init__(self, *, target, daemon):
            assert daemon
            waiting.append(target)

        def start(self):
            pass

    monkeypatch.setitem(instance.handle.__func__.__globals__, "threading", SimpleNamespace(Thread=Worker))
    result = dict(decks=[], totals=dict(new=0, learning=0, review=0))
    monkeypatch.setattr("learning_calendar.anki.read_review", lambda: result)
    instance.handle(dict(id=10, method="anki.read", params={}))
    assert not waiting
    assert any(row.get("id") == 10 and "켜세요" in row["error"] for row in output)

    instance.handle(dict(id=11, method="preferences.save", params=dict(anki_sync=True)))
    instance.handle(dict(id=12, method="anki.read", params={}))
    assert len(waiting) == 1 and not any(row.get("id") == 12 for row in output)
    waiting.pop()()
    assert dict(id=12, result=result) in output

    instance.handle(dict(id=13, method="anki.read", params={}))
    instance.handle(dict(id=14, method="preferences.save", params=dict(anki_sync=False)))
    instance.handle(dict(id=15, method="preferences.save", params=dict(anki_sync=True)))
    waiting.pop()()
    assert any(row.get("id") == 13 and "취소" in row["error"] for row in output)


@pytest.fixture
def developer_service(service):
    instance, output = service
    instance.handle(
        dict(
            id=900,
            method="preferences.save",
            params=dict(developer_mode=True, developer_acknowledged=True),
        )
    )
    output.clear()
    return service


def test_console_captures_failed_calix_requests_and_ui_errors(developer_service):
    instance, output = developer_service
    for identifier, method, params in [
        (1, "diagnostics.enable", {"enabled": True}),
        (2, "sync", {}),
        (3, "diagnostics.record", {"source": "ui", "level": "error", "message": "TypeError: api_key=example-key"}),
        (4, "diagnostics.read", {}),
        (5, "diagnostics.enable", {"enabled": False}),
        (6, "diagnostics.read", {}),
    ]:
        instance.handle(dict(id=identifier, method=method, params=params))
    captured = next(row["result"] for row in output if row.get("id") == 4)
    assert any(row["source"] == "engine" and row["level"] == "error" and "학교 로그인" in row["message"] for row in captured["rows"])
    assert any(row["source"] == "ui" and row["level"] == "error" and "[REDACTED]" in row["message"] for row in captured["rows"])
    assert "example-key" not in repr(captured)
    assert next(row["result"] for row in output if row.get("id") == 6) == {"enabled": False, "rows": []}


@pytest.mark.parametrize(
    "method", ["session.logout", "session.prepare", "session.import", "session.restore"]
)
def test_account_changes_are_blocked_while_collection_runs(service, method):
    instance, output = service
    instance.collector = object()
    instance.handle(dict(id=1, method=method, params={}))
    reply = next(row for row in output if row.get("id") == 1)
    assert "동기화가 끝난 뒤" in reply["error"]
    assert instance.collector is not None


def test_sync_requires_confirmed_login(service):
    instance, output = service
    instance.restore_token = "restore-in-progress"
    instance.handle(dict(id=1, method="sync", params={}))
    assert not instance.pending_sync
    assert not any(row.get("event") == "auth-required" for row in output)
    assert '학교 로그인' in next(row for row in output if row.get('id') == 1)['error']


def test_startup_reminder_waits_for_unlock_and_idle_sync(service, monkeypatch):
    instance, output = service
    api = instance.handle.__func__.__globals__["api"]
    locked = True
    monkeypatch.setattr(api.security, "state", lambda: {"locked": locked})
    checks = []

    def reminder(_api, trigger):
        checks.append(trigger)
        return {"urgent": False} if trigger == "startup" else None

    monkeypatch.setattr("learning_calendar.reminders.check", reminder)
    instance.reminders_ready = True
    instance.check_reminders()
    assert not checks and instance.startup_reminder_pending

    locked = False
    instance.task = SimpleNamespace(deleteLater=lambda: None)
    instance.check_reminders()
    assert not checks and instance.startup_reminder_pending
    instance.sync_finished()
    instance.check_reminders()
    assert checks == ["startup", "timer"]
    assert [row["payload"] for row in output if row.get("event") == "reminder"] == [{"urgent": False}]


def test_sync_reminder_survives_lock_and_ignores_stale_tokens(service, monkeypatch):
    instance, output = service
    api = instance.handle.__func__.__globals__["api"]
    locked = True
    monkeypatch.setattr(api.security, "state", lambda: {"locked": locked})
    instance.reminders_ready = True
    instance.startup_reminder_pending = False
    instance.sync_reminder_token = "current"
    checks = []

    def reminder(_api, trigger):
        checks.append(trigger)
        return {"urgent": False}

    monkeypatch.setattr("learning_calendar.reminders.check", reminder)
    instance.release_sync_reminder("stale")
    assert instance.released_sync_reminder_token is None
    instance.release_sync_reminder("current")
    assert not checks and instance.sync_reminder_token == "current"
    locked = False
    instance.check_reminders()
    instance.release_sync_reminder("current")
    assert checks == ["sync"] and instance.sync_reminder_token is None
    assert [row["payload"] for row in output if row.get("event") == "reminder"] == [{"urgent": False}]


@pytest.mark.parametrize('interactive', [True, False])
def test_login_syncs_only_after_interactive_authentication(service, monkeypatch, interactive):
    instance, output = service
    calls = []
    instance.restore_token = 'current'
    monkeypatch.setattr(instance, 'start_collector', lambda: calls.append(True))
    assert instance.accept_browser_identity(dict(owner='7', courses=[dict(id=2, name='Course')], interactive=interactive, token='current'))
    assert calls == ([True] if interactive else [])


def test_busy_stays_true_until_both_workers_finish(service):
    instance, output = service
    instance.collector = object()
    instance.task = SimpleNamespace(deleteLater=lambda: None)
    instance.publish_busy()
    instance.sync_finished()
    assert [row["busy"] for row in output if row.get("event") == "sync-state"] == [True]
    instance.collector = None
    instance.publish_busy()
    assert output[-1] == dict(event="sync-state", busy=False)


def test_bad_browser_packet_ends_collection_without_touching_data(service):
    instance, output = service
    instance.collector = "a" * 32
    instance.handle(
        dict(
            id=1,
            method="browser.complete",
            params=dict(runId=instance.collector, payload=[1]),
        )
    )
    assert instance.collector is None
    assert any(row.get("event") == "sync-error" for row in output)
    assert next(row for row in output if row.get("id") == 1).get("error")


def test_late_completion_from_cancelled_browser_is_ignored(service):
    instance, output = service
    instance.collector = "b" * 32
    assert instance.browser_complete(dict(runId="a" * 32, payload={})) is False
    assert instance.collector == "b" * 32


def test_cancelled_restore_cannot_reactivate_old_session(service):
    instance, output = service
    instance.restore_token = "old"
    instance.handle(dict(id=1, method="session.prepare", params={}))
    assert (
        instance.accept_browser_identity(
            dict(
                owner="7",
                courses=[dict(id=2, name="수업")],
                interactive=False,
                token="old",
            )
        )
        is False
    )
    assert not instance.logged_in


def test_restore_failure_opens_login_only_for_a_waiting_sync(service):
    instance, output = service
    instance.restore_token = "pending"
    instance.pending_sync = True
    instance.handle(
        dict(id=1, method="browser.restore.failed", params=dict(token="pending"))
    )
    assert instance.restore_token is None
    assert any(row.get("event") == "auth-required" for row in output)


def test_logging_can_be_enabled_during_collection(developer_service):
    instance, output = developer_service
    instance.collector = "c" * 32
    instance.handle(dict(id=1, method="diagnostics.enable", params={"enabled": True}))
    assert next(r for r in output if r.get("id") == 1)["result"] is True
    assert instance.collector == "c" * 32


def test_startup_update_checks_once_without_download(service):
    instance, output = service
    calls = []
    instance.updates = SimpleNamespace(
        phase="idle",
        state={"phase": "checking"},
        check=lambda **kwargs: calls.append(kwargs),
    )
    for request_id in (1, 2):
        instance.handle(dict(id=request_id, method="update.startup", params={}))
    assert calls == [{"automatic": True}]
    assert all("error" not in row for row in output if "id" in row)


def test_reopening_a_locked_app_rechecks_updates_without_overlapping(service):
    instance, output = service
    calls = []
    instance.handle(dict(id=90, method="security.setup", params=dict(
        password="Calix lifecycle fixture!", policy=dict(main=False, timetable=False, grades=False, idle_minutes=5),
    )))
    instance.handle(dict(id=91, method="security.lock", params={"scope": "main"}))
    assert all("error" not in row for row in output if row.get("id") in (90, 91))
    instance.updates = SimpleNamespace(
        phase="idle", state={"phase": "idle"}, check=lambda **kwargs: calls.append(kwargs),
    )
    instance.handle(dict(id=1, method="update.startup", params={}))
    instance.handle(dict(id=2, method="update.startup", params={"reopened": True}))
    instance.updates.phase = "downloading"
    instance.handle(dict(id=3, method="update.startup", params={"reopened": True}))
    instance.handle(dict(id=4, method="update.check", params={}))
    assert calls == [{"automatic": True}, {"automatic": True}]
    assert all("error" not in row for row in output if row.get("id") in (1, 2, 3))
    assert any(row.get("id") == 4 and "error" in row for row in output)


def test_developer_metrics_and_inspector_do_not_enable_logging(developer_service):
    instance, output = developer_service
    for request_id, method in enumerate(
        ("diagnostics.metrics", "diagnostics.snapshot"), 1
    ):
        instance.handle(dict(id=request_id, method=method, params={}))
    replies = [row for row in output if "id" in row]
    assert all("error" not in row for row in replies)
    assert replies[0]["result"]["rss_mb"] > 0
    assert replies[1]["result"]["logs"] == {"enabled": False, "rows": []}


def test_stop_invalidates_browser_run_and_ignores_late_results(service):
    instance, output = service
    run = "d" * 32
    instance.collector = run
    instance.handle(dict(id=1, method="sync.cancel", params={}))
    assert instance.collector is None and not instance.pending_sync
    assert any(r.get("event") == "browser-cancel" and r["runId"] == run for r in output)
    assert instance.browser_complete(dict(runId=run, payload={})) is False


def test_force_restarts_collector_with_a_new_run_id(developer_service):
    instance, output = developer_service
    run = "e" * 32
    instance.collector = run
    instance.logged_in = True
    instance.handle(dict(id=1, method="sync.force", params={}))
    assert instance.collector and instance.collector != run
    events = [
        r["event"]
        for r in output
        if r.get("event") in ("browser-cancel", "browser-collect")
    ]
    assert events == ["browser-cancel", "browser-collect"]


def test_force_waits_for_saving_worker_before_restart(developer_service):
    instance, output = developer_service
    cancelled = []
    instance.logged_in = True
    instance.task = SimpleNamespace(
        cancel=lambda: cancelled.append(True), deleteLater=lambda: None
    )
    instance.handle(dict(id=1, method="sync.force", params={}))
    assert cancelled == [True] and instance.restart_sync and instance.collector is None
    instance.sync_finished()
    assert instance.task is None and not instance.restart_sync and instance.collector


def test_stop_clears_a_pending_force_restart(developer_service):
    instance, output = developer_service
    instance.logged_in = True
    instance.task = SimpleNamespace(cancel=lambda: None, deleteLater=lambda: None)
    instance.handle(dict(id=1, method="sync.force", params={}))
    instance.handle(dict(id=2, method="sync.cancel", params={}))
    instance.sync_finished()
    assert instance.collector is None and not instance.restart_sync


def test_developer_sync_request_reports_busy_without_starting_another_run(
    developer_service,
):
    instance, output = developer_service
    instance.collector = "f" * 32
    instance.handle(dict(id=1, method="sync.request", params={}))
    assert next(r for r in output if r.get("id") == 1)["result"] == dict(
        alreadyRunning=True
    )
    assert not any(r.get("event") == "browser-collect" for r in output)


@pytest.mark.parametrize(
    "method",
    [
        "diagnostics.enable",
        "diagnostics.snapshot",
        "diagnostics.metrics",
        "sync.force",
        "sync.request",
        "developer.maintenance.start",
    ],
)
def test_developer_requests_are_blocked_before_opt_in(service, method):
    instance, output = service
    instance.handle(
        dict(
            id=1,
            method=method,
            params=dict(enabled=True, action="optimize", confirmed=True),
        )
    )
    reply = next(row for row in output if row.get("id") == 1)
    assert reply["error"] == "Developer Mode is disabled."
    assert instance.maintenance is None and instance.collector is None


def test_maintenance_rejects_requests_during_sync(developer_service):
    instance, output = developer_service
    instance.collector = "a" * 32
    instance.handle(
        dict(
            id=1,
            method="developer.maintenance.start",
            params=dict(action="optimize", confirmed=True),
        )
    )
    assert (
        "active operation" in next(row for row in output if row.get("id") == 1)["error"]
    )
    assert instance.maintenance is None
