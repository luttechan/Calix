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
            self.collector = None
            self.collector_received = False
            self.collector_buffer = bytearray()
            self.validator = None
            self.validation_generation = 0
            self.pending_sync = False
            self.logged_in = False
            self.closing = False
            self.closed = False
            self.updates = None
            self.install_on_exit = False
            self.input = None
            self.reported_busy = None
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
            busy = bool(self.task or self.collector or self.pending_sync)
            if busy != self.reported_busy:
                self.reported_busy = busy
                self.notify("sync-state", busy=busy)

        def notify(self, event, **payload):
            if (event.startswith("sync-") and event != "sync-state") or event in (
                "session-error",
                "authentication",
            ):
                diagnostics.add(f"{event}: {payload.get('message', '')}")
            emit(dict(event=event, **payload))

        def handle(self, request):
            reply = request.pop("_reply", None)
            try:
                if type(request.get("id")) is not int or not isinstance(
                    request.get("params", {}), dict
                ):
                    raise ValueError("요청을 확인하세요.")
                method, params = request.get("method"), request.get("params", {})
                if self.closing and method != "quit":
                    raise ValueError("종료 중입니다.")
                if method in (
                    "session.prepare",
                    "session.import",
                    "session.restore",
                    "session.logout",
                ) and (self.task or self.collector):
                    raise ValueError("동기화가 끝난 뒤 로그인 상태를 변경하세요.")
                if method == "diagnostics.enable":
                    if params.get("enabled") is True and (
                        self.task or self.collector or self.pending_sync
                    ):
                        raise ValueError("로그 수집을 먼저 켠 뒤 동기화하세요.")
                    result = diagnostics.set_enabled(params.get("enabled"))

                elif method == "diagnostics.record":
                    diagnostics.add(str(params.get("message", ""))[:4096])
                    result = True
                elif method == "diagnostics.read":
                    after = params.get("after", 0)
                    if type(after) is not int or after < 0:
                        raise ValueError("로그 위치를 확인하세요.")
                    result = diagnostics.read(after)
                elif method == "engine.state":
                    result = dict(
                        loggedIn=self.logged_in,
                        busy=bool(self.task or self.collector or self.pending_sync),
                    )
                elif method == "browser.identity":
                    if self.task or self.collector:
                        raise ValueError("동기화가 끝난 뒤 로그인 상태를 변경하세요.")
                    from engine_webview import identity

                    owner, _courses = identity(params)
                    api.activate_account(owner)
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
                    result = True
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
                            self.notify("sync-progress", message=message)
                elif method == "session.import":
                    raise ValueError("학교 로그인 창에서 완료를 누르세요.")
                    result = True
                elif method == "session.restore":
                    result = False
                elif method == "session.prepare":
                    self.validation_generation += 1
                    if self.validator:
                        self.validator.cancel()
                    result = True
                elif method == "session.logout":
                    self.validation_generation += 1
                    if self.validator:
                        self.validator.cancel()
                    (folder / "canvas_session.dpapi").unlink(missing_ok=True)
                    self.logged_in = False
                    self.pending_sync = False
                    self.notify("authentication", loggedIn=False)
                    result = True
                elif method == "session.cancel":
                    self.validation_generation += 1
                    self.pending_sync = False
                    if self.validator:
                        self.validator.cancel()
                    self.notify("auth-cancelled")
                    result = True
                elif method == "login":
                    self.notify("auth-required")
                    result = True
                elif method == "sync":
                    self.sync()
                    result = True
                elif method.startswith("update."):
                    if self.updates is None:
                        from engine_updates import UpdateService

                        self.updates = UpdateService(self.notify, self)
                    if method == "update.state":
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
                    if self.task or self.collector:
                        raise ValueError("진행 중인 작업을 마친 뒤 초기화하세요.")
                    self.validation_generation += 1
                    if self.validator:
                        self.validator.cancel()
                    self.pending_sync = False
                    result = api.dispatch(method, params)
                    self.logged_in = False
                    self.notify("auth-cancelled")
                    self.notify("authentication", loggedIn=False)
                    self.notify("data-changed")
                else:
                    if method.startswith("backup.") and (
                        self.task or self.collector or self.validator
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

        def sync(self):
            diagnostics.add("동기화 요청")
            if self.task or self.collector or self.pending_sync:
                raise ValueError("동기화 중입니다.")
            if not self.logged_in:
                self.pending_sync = True
                if not self.validator:
                    self.notify("auth-required")
                return
            self.start_collector()

        def start_collector(self):
            self.collector = secrets.token_hex(16)
            self.collection_timer.start(900000)
            diagnostics.add("WebView2 로그인 프로필에서 수집 시작")
            self.notify("browser-collect", runId=self.collector)
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

        def synced(self, result):
            api.switch_store(result["path"])
            self.notify("data-changed")
            self.notify(
                "sync-progress", message=result.get("sync_summary") or "동기화 완료"
            )

        def sync_finished(self):
            task, self.task = self.task, None
            if task:
                task.deleteLater()
            self.publish_busy()
            if self.closing:
                self.finish_shutdown()

        def shutdown(self):
            if self.closing:
                return
            self.closing = True
            self.validation_generation += 1
            if self.input:
                self.input.stop()
            if self.validator:
                self.validator.cancel()
            if self.task:
                self.task.cancel()
            if self.collector:
                self.notify("browser-cancel", runId=self.collector)
                self.collector = None
                self.collection_timer.stop()
            if self.updates:
                self.updates.cancel(keep_installer=self.install_on_exit)
            self.finish_shutdown()

        def finish_shutdown(self):
            if self.closed or self.task or self.collector or self.validator:
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
