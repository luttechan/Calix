"""Exercise the actual service class with offline collaborators."""

import ast
import json
import logging
import sys
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
    instance.validator = object()
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


def test_bad_collector_packet_reports_error_instead_of_crashing(service):
    instance, output = service

    class Event:
        def connect(self, callback):
            self.callback = callback

    class Process:
        def __init__(self):
            self.readyReadStandardOutput = Event()
            self.readyReadStandardError = Event()
            self.finished = Event()
            self.errorOccurred = Event()
            self.killed = False

        def processEnvironment(self):
            return QProcessEnvironment()

        def setProcessEnvironment(self, environment):
            pass

        def readAllStandardOutput(self):
            return b'{"event":"videos_collected","snapshot":[1]}\n'

        def kill(self):
            self.killed = True

        def start(self):
            self.readyReadStandardOutput.callback()

    process = Process()
    instance.child = lambda args: process
    instance.start_collector()
    assert process.killed
    assert any(row.get("event") == "sync-error" for row in output)
