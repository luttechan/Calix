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
    namespace = dict(
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
