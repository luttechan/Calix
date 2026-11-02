"""Exercise the actual service class with offline collaborators."""

import ast
import json
import logging
import sys
import secrets
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


def test_sync_waits_for_existing_login_validation(service):
    instance, output = service
    instance.restore_token = "restore-in-progress"
    instance.handle(dict(id=1, method="sync", params={}))
    assert instance.pending_sync
    assert not any(row.get("event") == "auth-required" for row in output)
    assert any(row.get("event") == "sync-state" and row["busy"] for row in output)


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
