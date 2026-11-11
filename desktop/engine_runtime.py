"""Desktop service lifecycle. No interactive Qt login or update windows."""

import argparse
import json
import logging
import os
import subprocess
import sys
import threading
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from learning_calendar.bootstrap import configure_runtime

configure_runtime()


def data_folder():
    return (
        Path(os.environ.get("APPDATA", str(Path.home() / "AppData/Roaming")))
        / "LutteLaurent/Calix"
    )


def main():
    if sys.stdout is not None:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir")
    parser.add_argument("--dev-http", type=int)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--utility", choices=["install"])
    parser.add_argument("--installer")
    parser.add_argument("--digest")
    parser.add_argument("--wait-pid", type=int)
    args = parser.parse_args()
    folder = Path(args.data_dir) if args.data_dir else data_folder()
    if args.utility:
        from engine_utility import install

        return install(args.installer, args.digest, args.wait_pid)
    from PySide6.QtCore import (
        QCoreApplication,
        QObject,
        Signal,
        QTimer,
    )
    from engine_api import EngineAPI
    from engine_transport import StdioInput

    app = QCoreApplication([])
    app.setApplicationName("Calix")
    app.setOrganizationName("LutteLaurent")
    if not args.data_dir:
        from learning_calendar.paths import migrate_legacy_data

        migrate_legacy_data(folder)
    from engine_logging import configure

    configure(folder)
    from engine_diagnostics import Diagnostics

    diagnostics = Diagnostics()
    logging.getLogger().addHandler(diagnostics)
    restore_trace = diagnostics.install_http_trace()
    api = EngineAPI(folder)
    if args.demo:
        if not args.data_dir:
            raise ValueError("Demo requires an isolated data directory")
        from learning_calendar.demo import data

        courses, batches = data()
        api.store.apply_batch(courses, batches)
        if not api.store.timetable():
            for i, course in enumerate(courses[:5]):
                api.store.add_timetable(
                    course.id, i, "09:00", "10:30", "김교수", "A201"
                )
    output_lock = threading.Lock()

    def emit(value):
        if args.dev_http:
            return
        with output_lock:
            sys.stdout.write(
                json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n"
            )
            sys.stdout.flush()

    class Service(QObject):
        incoming = Signal(object)

        def __init__(self):
            super().__init__()
            self.incoming.connect(self.handle)
            self.task = None
            self.maintenance = None
            self.maintenance_state = dict(phase="idle")
            self.collector = None
            self.restore_token = None
            self.pending_sync = False
            self.restart_sync = False
            self.logged_in = False
            self.closing = False
            self.closed = False
            self.updates = None
            self.startup_update_checked = False
            self.install_on_exit = False
            self.input = None
            self.reported_busy = None
            self.reminders_ready = False
            self.sync_reminder_token = None
            self.reminder_timer = QTimer(self)
            self.reminder_timer.setInterval(30000)
            self.reminder_timer.timeout.connect(lambda: self.check_reminders("timer"))
            self.reminder_timer.start()
            self.collection_timer = QTimer(self)
            self.collection_timer.setSingleShot(True)
            self.collection_timer.timeout.connect(
                lambda: self.browser_failed(
                    {"runId": self.collector, "message": "수집 시간이 초과됐습니다."}
                )
            )

        def publish_busy(self):
            if self.closing:
                return
            busy = bool(
                self.task or self.collector or self.pending_sync or self.restart_sync
            )
            if busy != self.reported_busy:
                self.reported_busy = busy
                self.notify("sync-state", busy=busy)

        def notify(self, event, **payload):
            if (event.startswith("sync-") and event != "sync-state") or event in (
                "session-error",
                "authentication",
            ):
                diagnostics.add(f"{event}: {payload.get('message', '')}")
            if event == "reminder" and api.security.state()["locked"]:
                return
            emit(dict(event=event, **payload))

        def handle(self, request):
            reply = request.pop("_reply", None)
            try:
                if type(request.get("id")) is not int or not isinstance(
                    request.get("params", {}), dict
                ):
                    raise ValueError("요청을 확인하세요.")
                method, params = request.get("method"), request.get("params", {})
                api.security.require(method)
                developer_enabled = (
                    api.settings.get("developer_mode") is True
                    and api.settings.get("developer_acknowledged") is True
                )
                if isinstance(method, str) and (
                    method.startswith(("diagnostics.", "developer."))
                    or method in ("sync.force", "sync.request")
                ):
                    cleanup = (
                        method == "diagnostics.enable"
                        and params.get("enabled") is False
                    ) or method == "diagnostics.read"
                    if not developer_enabled and not cleanup:
                        raise ValueError("Developer Mode is disabled.")
                if (
                    self.maintenance
                    and method
                    not in ("bootstrap", "engine.state", "quit", "preferences.save")
                    and not str(method).startswith(
                        ("diagnostics.", "developer.maintenance.state")
                    )
                ):
                    raise ValueError("Database maintenance is running.")
                if isinstance(method, str) and not method.startswith("diagnostics."):
                    diagnostics.add(f"RPC {method[:100]}")
                if self.closing and method != "quit":
                    raise ValueError("종료 중입니다.")
                if method in (
                    "session.prepare",
                    "session.import",
                    "session.restore",
                    "session.logout",
                ) and (self.task or self.collector):
                    raise ValueError("동기화가 끝난 뒤 로그인 상태를 변경하세요.")
                if method in ("security.setup", "security.configure"):
                    if self.task or self.collector or self.maintenance or self.restore_token:
                        raise ValueError("진행 중인 작업을 마친 뒤 잠금을 설정하세요.")
                    result = api.dispatch(method, params)
                elif method == "developer.maintenance.state":
                    result = self.maintenance_state
                elif method == "developer.maintenance.start":
                    from engine_maintenance import MaintenanceTask, ACTIONS

                    action = params.get("action")
                    if action not in ACTIONS or params.get("confirmed") is not True:
                        raise ValueError("Confirm the maintenance operation first.")
                    if (
                        self.maintenance
                        or self.task
                        or self.collector
                        or self.restore_token
                        or self.pending_sync
                        or self.restart_sync
                    ):
                        raise ValueError("Wait for the active operation to finish.")
                    self.maintenance_state = dict(phase="working", action=action)
                    self.maintenance = MaintenanceTask(api.store.path, action, self)
                    self.maintenance.success.connect(
                        lambda report: self.maintenance_result(
                            dict(phase="complete", report=report)
                        )
                    )
                    self.maintenance.error.connect(
                        lambda message: self.maintenance_result(
                            dict(phase="error", message=message)
                        )
                    )
                    self.maintenance.finished.connect(self.maintenance_finished)
                    self.maintenance.start()
                    result = self.maintenance_state
                elif method == "diagnostics.enable":
                    result = diagnostics.set_enabled(params.get("enabled"))

                elif method == "diagnostics.record":
                    diagnostics.add(str(params.get("message", ""))[:4096])
                    result = True
                elif method == "diagnostics.read":
                    after = params.get("after", 0)
                    if type(after) is not int or after < 0:
                        raise ValueError("로그 위치를 확인하세요.")
                    result = diagnostics.read(after)
                elif method == "diagnostics.metrics":
                    result = diagnostics.metrics()
                elif method == "diagnostics.snapshot":
                    result = diagnostics.snapshot(
                        api,
                        self.task
                        or self.collector
                        or self.pending_sync
                        or self.restart_sync,
                    )
                elif method == "engine.state":
                    result = dict(
                        loggedIn=self.logged_in,
                        busy=bool(
                            self.task
                            or self.collector
                            or self.pending_sync
                            or self.restart_sync
                        ),
                    )
                elif method == "browser.restore.begin":
                    if (
                        self.task
                        or self.collector
                        or self.pending_sync
                        or self.restart_sync
                    ):
                        raise ValueError("진행 중인 작업을 마친 뒤 확인하세요.")
                    self.restore_token = secrets.token_hex(16)
                    result = self.restore_token
                elif method == "browser.restore.failed":
                    result = bool(
                        self.restore_token and params.get("token") == self.restore_token
                    )
                    if result:
                        self.restore_token = None
                        self.logged_in = False
                        self.notify("authentication", loggedIn=False)
                        if self.pending_sync:
                            self.notify("auth-required")
                elif method == "browser.identity":
                    result = self.accept_browser_identity(params)
                elif method == "browser.complete":
                    result = self.browser_complete(params)
                elif method == "browser.failed":
                    result = self.browser_failed(params)
                elif method == "browser.progress":
                    result = (
                        params.get("runId") == self.collector
                        and self.collector is not None
                    )
                    if result:
                        message = str(params.get("message", ""))[:300]
                        if params.get("log") is True:
                            diagnostics.add(message)
                        else:
                            self.notify(
                                "sync-progress",
                                message=message,
                                current=params.get("current"),
                                total=params.get("total"),
                                remainingSeconds=params.get("remainingSeconds"),
                            )
                elif method == "session.import":
                    raise ValueError("학교 로그인 창에서 완료를 누르세요.")
                elif method == "session.restore":
                    result = False
                elif method == "session.prepare":
                    self.restore_token = None
                    result = True
                elif method == "session.logout":
                    self.sync_reminder_token = None
                    self.restore_token = None
                    (folder / "canvas_session.dpapi").unlink(missing_ok=True)
                    self.logged_in = False
                    self.pending_sync = False
                    self.notify("authentication", loggedIn=False)
                    result = True
                elif method == "session.cancel":
                    self.restore_token = None
                    self.pending_sync = False
                    self.notify("auth-cancelled")
                    result = True
                elif method == "login":
                    self.notify("auth-required")
                    result = True
                elif method == "sync.cancel":
                    self.stop_sync()
                    result = True
                elif method == "reminders.sync-ready":
                    if (
                        params.get("token") == self.sync_reminder_token
                        and self.sync_reminder_token
                    ):
                        self.sync_reminder_token = None
                        self.check_reminders("sync")
                    result = True
                elif method == "reminders.ready":
                    if not self.reminders_ready:
                        self.reminders_ready = True
                        self.check_reminders("startup")
                    result = True
                elif method == "sync.force":
                    self.stop_sync(restart=True)
                    result = True
                elif method == "sync.request":
                    busy = bool(
                        self.task
                        or self.collector
                        or self.pending_sync
                        or self.restart_sync
                    )
                    if not busy:
                        self.sync()
                    result = dict(alreadyRunning=busy)
                elif method == "sync":
                    self.sync()
                    result = True
                elif method.startswith("update."):
                    if self.updates is None:
                        from engine_updates import UpdateService

                        self.updates = UpdateService(self.notify, self)
                    if method == "update.startup":
                        if not self.startup_update_checked:
                            self.startup_update_checked = True
                            if self.updates.phase not in (
                                "checking",
                                "downloading",
                                "ready",
                            ):
                                self.updates.check(automatic=True)
                        result = self.updates.state
                    elif method == "update.state":
                        result = self.updates.state
                    elif method == "update.check":
                        self.updates.check()
                        result = True
                    elif method == "update.download":
                        self.updates.download()
                        result = True
                    elif method == "update.cancel":
                        self.updates.cancel(
                            keep_installer=params.get("keepReady") is True
                        )
                        if not self.updates.installer:
                            self.updates.publish("idle")
                        result = True
                    else:
                        raise ValueError("지원하지 않는 요청입니다.")
                elif method == "event.open":
                    from learning_calendar.parsers import safe_url
                    import webbrowser

                    url = api.event(params["key"]).url
                    if not safe_url(url):
                        raise ValueError("학교 일정 주소를 확인하세요.")
                    webbrowser.open(url)
                    result = True
                elif method == "app.open":
                    import webbrowser

                    links = {
                        "github": "https://github.com/luttechan/Calix",
                        "family": "https://luttechan.github.io/lutte_family/",
                        "guide": "https://luttechan.github.io/calix/guide/",
                        "grade45": "https://www.bufs.ac.kr/bbs/board.php?bo_table=university_rules&wr_id=43",
                        "grade43": "https://rules.yonsei.ac.kr/regulations/2a85e62f-029e-46d6-92c7-edefce6432c0",
                        "grade40": "https://registrar.berkeley.edu/faculty-staff-resources/grade-definitions/",
                        "releases": "https://github.com/luttechan/Calix/releases",
                    }
                    if params.get("page") not in links:
                        raise ValueError("주소를 확인하세요.")
                    webbrowser.open(links[params["page"]])
                    result = True
                elif method == "quit":
                    self.install_on_exit = params.get("install") is True
                    self.shutdown()
                    result = True
                elif method == "data.reset":
                    self.sync_reminder_token = None
                    if self.task or self.collector:
                        raise ValueError("진행 중인 작업을 마친 뒤 초기화하세요.")
                    self.restore_token = None
                    self.pending_sync = False
                    result = api.dispatch(method, params)
                    self.logged_in = False
                    self.notify("auth-cancelled")
                    self.notify("authentication", loggedIn=False)
                    self.notify("data-changed")
                elif method == "preferences.save":
                    result = api.dispatch(method, params)
                    if not api.settings.get("developer_mode"):
                        diagnostics.set_enabled(False)
                        if self.maintenance:
                            self.maintenance.cancel()
                    self.notify(
                        "developer-mode",
                        enabled=api.settings.get("developer_mode") is True,
                    )
                else:
                    if method.startswith("backup.") and (
                        self.task or self.collector or self.restore_token
                    ):
                        raise ValueError("동기화가 끝난 뒤 다시 시도하세요.")
                    result = api.dispatch(method, params)
                response = dict(id=request["id"], result=result)
            except (KeyError, TypeError, ValueError) as error:
                response = dict(
                    id=request.get("id"),
                    error=(
                        str(error)
                        if isinstance(error, ValueError)
                        else "입력 내용을 확인하세요."
                    ),
                )
            except Exception:
                logging.exception("Desktop request failed: %s", request.get("method"))
                response = dict(
                    id=request.get("id"), error="요청을 처리하지 못했습니다."
                )
            self.publish_busy()
            if reply:
                reply(response)
            else:
                emit(response)

        def accept_browser_identity(self, params):
            if params.get("interactive") is not True and (
                not self.restore_token or params.get("token") != self.restore_token
            ):
                return False
            if self.task or self.collector:
                raise ValueError("동기화가 끝난 뒤 로그인 상태를 변경하세요.")
            from engine_webview import identity

            owner, _courses = identity(params)
            api.activate_account(owner)
            self.restore_token = None
            self.logged_in = True
            self.notify(
                "authentication",
                loggedIn=True,
                interactive=params.get("interactive") is True,
            )
            self.notify("data-changed")
            if self.pending_sync:
                self.pending_sync = False
                self.start_collector()
            return True

        def sync(self):
            self.sync_reminder_token = None
            diagnostics.add("Synchronization requested")
            if self.task or self.collector or self.pending_sync or self.restart_sync:
                raise ValueError("동기화 중입니다.")
            if not self.logged_in:
                self.pending_sync = True
                if not self.restore_token:
                    self.notify("auth-required")
                return
            self.start_collector()

        def stop_sync(self, restart=False):
            self.restart_sync = restart
            self.restore_token = None
            self.pending_sync = False
            if self.collector:
                run = self.collector
                self.collector = None
                self.collection_timer.stop()
                self.notify("browser-cancel", runId=run)
            if self.task:
                self.task.cancel()
            self.notify(
                "sync-progress",
                message=(
                    "Force Synchronizing: aborting active run; collector restart queued."
                    if restart
                    else "동기화를 중단했습니다."
                ),
            )
            if not restart:
                self.notify("sync-cancelled", message="동기화를 중단했습니다.")
            if restart and not self.task:
                self.restart_sync = False
                self.sync()
            self.publish_busy()

        def start_collector(self):
            self.collector = secrets.token_hex(16)
            self.collection_timer.start(210000)
            diagnostics.add("Collector started with the WebView2 login profile")
            from learning_calendar.incremental import cache_state

            self.notify("sync-started", runId=self.collector)
            self.notify(
                "browser-collect",
                runId=self.collector,
                cache=cache_state(api.store),
                attendanceSync=api.settings.get("attendance_sync") is True,
            )
            self.notify("sync-progress", message="학교 일정 확인 중")

        def browser_failed(self, params):
            if not self.collector or params.get("runId") != self.collector:
                return False
            run = self.collector
            self.collector = None
            self.collection_timer.stop()
            self.notify("browser-cancel", runId=run)
            if params.get("authentication") is True:
                self.logged_in = False
                self.notify("authentication", loggedIn=False)
            self.notify(
                "sync-error",
                message=str(
                    params.get("message") or "학교 일정을 확인하지 못했습니다."
                )[:300],
            )
            self.publish_busy()
            return True

        def browser_complete(self, params):
            if not self.collector or params.get("runId") != self.collector:
                return False
            payload = params.get("payload")
            from engine_webview import identity

            try:
                owner, _courses = identity(payload)
                if owner != api.store.get_meta("canvas_user_id"):
                    raise ValueError("수집한 학교 계정이 일치하지 않습니다.")
                if payload.get("transport") != "webview2" or not isinstance(
                    payload.get("results"), list
                ):
                    raise ValueError("수집 응답을 확인하지 못했습니다.")
            except (ValueError, TypeError):
                self.browser_failed(
                    dict(
                        runId=self.collector,
                        message="수집 응답과 학교 계정을 확인하지 못했습니다.",
                    )
                )
                raise
            self.collector = None
            self.collection_timer.stop()
            from engine_webview import BrowserSyncTask

            self.task = BrowserSyncTask(payload, api.store.path, self)
            self.task.progress.connect(
                lambda message: self.notify("sync-progress", message=message)
            )
            self.task.success.connect(self.synced)
            self.task.error.connect(
                lambda message: self.notify("sync-error", message=message)
            )
            self.task.authentication_required.connect(
                lambda message: self.notify("sync-error", message=message)
            )
            self.task.finished.connect(self.sync_finished)
            self.task.start()
            return True

        def check_reminders(self, trigger):
            if (
                self.closing
                or not self.reminders_ready
                or self.sync_reminder_token
                or self.task
                or self.collector
            ):
                return
            from learning_calendar.reminders import check

            try:
                payload = check(api, trigger)
                if payload:
                    self.notify("reminder", payload=payload)
            except Exception as error:
                diagnostics.add(f"Reminder failed: {type(error).__name__}")

        def synced(self, result):
            api.switch_store(result["path"])
            self.notify("data-changed")
            token = secrets.token_hex(16)
            self.sync_reminder_token = token

            def fallback():
                if self.sync_reminder_token == token:
                    self.sync_reminder_token = None
                    self.check_reminders("sync")

            QTimer.singleShot(20000, fallback)
            self.notify(
                "sync-complete",
                reminderToken=token,
                message=result.get("sync_summary") or "동기화 완료",
                stats=result.get("stats", {}),
                warnings=result.get("warnings", []),
            )

        def maintenance_result(self, state):
            self.maintenance_state = state
            self.notify("developer-maintenance", **state)

        def maintenance_finished(self):
            task, self.maintenance = self.maintenance, None
            if task:
                task.deleteLater()
            if self.closing:
                self.finish_shutdown()

        def sync_finished(self):
            task, self.task = self.task, None
            if task:
                task.deleteLater()
            if self.restart_sync and not self.closing:
                self.restart_sync = False
                self.sync()
            self.publish_busy()
            if self.closing:
                self.finish_shutdown()

        def shutdown(self):
            if self.closing:
                return
            self.closing = True
            self.reminder_timer.stop()
            self.restart_sync = False
            self.restore_token = None
            if self.input:
                self.input.stop()
            if self.task:
                self.task.cancel()
            if self.maintenance:
                self.maintenance.cancel()
            if self.collector:
                self.notify("browser-cancel", runId=self.collector)
                self.collector = None
                self.collection_timer.stop()
            if self.updates:
                self.updates.cancel(keep_installer=self.install_on_exit)
            self.finish_shutdown()

        def finish_shutdown(self):
            if (
                self.closed
                or self.task
                or self.collector
                or self.restore_token
                or self.maintenance
            ):
                return
            self.closed = True
            api.close()
            if self.install_on_exit and self.updates and self.updates.installer:
                path, digest = self.updates.installer
                prefix = (
                    []
                    if getattr(sys, "frozen", False)
                    else [str(ROOT / "desktop/engine_main.py")]
                )
                subprocess.Popen(
                    [
                        sys.executable,
                        *prefix,
                        "--utility",
                        "install",
                        "--installer",
                        path,
                        "--digest",
                        digest,
                        "--wait-pid",
                        str(os.getppid()),
                    ],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            QTimer.singleShot(0, app.quit)

    service = Service()
    http = None
    if args.dev_http:
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        token = os.environ.get("CALIX_DEV_TOKEN", "")
        if len(token) < 32:
            raise ValueError("Set a development token of at least 32 characters")

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    self.send_error(400)
                    return
                if (
                    self.path != "/api"
                    or self.headers.get("X-Calix-Token") != token
                    or not 0 < length <= 2 * 1024 * 1024
                    or self.headers.get_content_type() != "application/json"
                    or self.headers.get("Origin") not in (None, "http://127.0.0.1:5173")
                ):
                    self.send_error(403)
                    return
                try:
                    request = json.loads(self.rfile.read(length))
                except ValueError:
                    self.send_error(400)
                    return
                if not isinstance(request, dict):
                    self.send_error(400)
                    return
                ready = threading.Event()
                result = []
                request["_reply"] = lambda value: (result.append(value), ready.set())
                service.incoming.emit(request)
                if not ready.wait(90):
                    self.send_error(504)
                    return
                payload = json.dumps(result[0], ensure_ascii=False).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(payload)

        http = ThreadingHTTPServer(("127.0.0.1", args.dev_http), Handler)
        threading.Thread(target=http.serve_forever, daemon=True).start()
    else:
        service.input = StdioInput(
            service.incoming.emit,
            lambda message: emit(dict(id=None, error=message)),
            service,
        )
    code = app.exec()
    if http:
        http.shutdown()
    restore_trace()
    logging.getLogger().removeHandler(diagnostics)
    return code
