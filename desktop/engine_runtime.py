"""Desktop service lifecycle. No interactive Qt login or update windows."""

import argparse
import json
import logging
import os
import subprocess
import sys
import threading
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
    parser.add_argument("--collect", action="store_true")
    parser.add_argument("--collector-check")
    parser.add_argument("--dev-http", type=int)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--utility", choices=["install"])
    parser.add_argument("--installer")
    parser.add_argument("--digest")
    parser.add_argument("--wait-pid", type=int)
    args = parser.parse_args()
    folder = Path(args.data_dir) if args.data_dir else data_folder()
    if args.collector_check:
        from engine_browser_check import run

        return run(args.collector_check)
    if args.collect:
        from engine_collector import run

        return run(folder)
    if args.utility:
        from engine_utility import install

        return install(args.installer, args.digest, args.wait_pid)
    from PySide6.QtCore import (
        QCoreApplication,
        QObject,
        Signal,
        QTimer,
        QProcess,
        QProcessEnvironment,
    )
    from engine_api import EngineAPI
    from engine_transport import StdioInput
    from engine_sessions import import_cookie_records, SessionValidation
    from learning_calendar.cookies import (
        read_cookies,
        write_cookies,
        canvas_session_available,
    )

    app = QCoreApplication([])
    app.setApplicationName("Calix")
    app.setOrganizationName("LutteLaurent")
    if not args.data_dir:
        from learning_calendar.paths import migrate_legacy_data

        migrate_legacy_data(folder)
    from engine_logging import configure

    configure(folder)
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

        def notify(self, event, **payload):
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
                if method == "engine.state":
                    result = dict(
                        loggedIn=self.logged_in,
                        busy=bool(self.task or self.collector or self.pending_sync),
                    )
                elif method == "session.import":
                    self.validate(import_cookie_records(params.get("cookies")))
                    result = True
                elif method == "session.restore":
                    rows = read_cookies(folder / "canvas_session.dpapi")
                    result = canvas_session_available(rows)
                    if result:
                        self.validate(rows, quiet=True)
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
            if reply:
                reply(response)
            else:
                emit(response)

        def validate(self, rows, quiet=False):
            if self.validator:
                raise ValueError("로그인 상태를 확인 중입니다.")
            self.validation_generation += 1
            generation = self.validation_generation
            task = SessionValidation(rows, self)
            self.validator = task

            def checked(identity):
                if self.closing or generation != self.validation_generation:
                    return
                try:
                    changed = api.activate_account(identity["owner"])
                    if changed:
                        self.notify("data-changed")
                    write_cookies(folder / "canvas_session.dpapi", rows)
                except Exception:
                    logging.exception("Verified session could not be saved")
                    self.pending_sync = False
                    self.notify(
                        "session-error",
                        message="로그인 정보를 저장하지 못했습니다. 다시 시도하세요.",
                    )
                    self.notify("auth-cancelled")
                    return
                self.logged_in = True
                self.notify("authentication", loggedIn=True, interactive=not quiet)
                if self.pending_sync:
                    self.pending_sync = False
                    self.start_collector()

            def failed(message):
                if self.closing or generation != self.validation_generation:
                    return
                self.logged_in = False
                self.pending_sync = False
                self.notify("authentication", loggedIn=False)
                if not quiet:
                    self.notify("session-error", message=message)
                self.notify("auth-cancelled")

            def finished():
                self.validator = None
                task.deleteLater()
                if self.closing:
                    self.finish_shutdown()

            task.checked.connect(checked)
            task.failed.connect(failed)
            task.finished.connect(finished)
            task.start()

        def child(self, arguments):
            process = QProcess(self)
            environment = QProcessEnvironment.systemEnvironment()
            if getattr(sys, "frozen", False):
                environment.insert("PYINSTALLER_RESET_ENVIRONMENT", "1")
            process.setProcessEnvironment(environment)
            process.setProgram(sys.executable)
            prefix = (
                []
                if getattr(sys, "frozen", False)
                else [str(ROOT / "desktop/engine_main.py")]
            )
            process.setArguments(prefix + arguments + ["--data-dir", str(folder)])
            return process

        def sync(self):
            if self.task or self.collector or self.pending_sync:
                raise ValueError("동기화 중입니다.")
            if not self.logged_in:
                self.pending_sync = True
                self.notify("auth-required")
                return
            self.start_collector()

        def start_collector(self):
            process = self.child(["--collect"])
            self.collector = process
            self.collector_received = False
            self.collector_buffer.clear()

            def read():
                self.collector_buffer.extend(bytes(process.readAllStandardOutput()))
                if len(self.collector_buffer) > 8 * 1024 * 1024:
                    self.notify("sync-error", message="주차학습 응답이 너무 큽니다.")
                    process.kill()
                    return
                while b"\n" in self.collector_buffer:
                    line, _, rest = self.collector_buffer.partition(b"\n")
                    self.collector_buffer = bytearray(rest)
                    try:
                        value = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(value, dict):
                        continue
                    event = value.get("event")
                    if event == "videos_collected":
                        self.collector_received = True
                        self.start_sync(value.get("snapshot"))
                    elif event == "collection_progress":
                        self.notify(
                            "sync-progress",
                            message=value.get("message", "주차학습 확인 중"),
                        )
                    elif event in ("collection_auth_required", "collection_error"):
                        self.collector_received = True
                        if event == "collection_auth_required":
                            self.logged_in = False
                            self.notify("authentication", loggedIn=False)
                        self.notify(
                            "sync-error",
                            message=value.get("message", "주차학습 확인 실패"),
                        )

            def finished(*_):
                if self.collector is not process:
                    return
                read()
                self.collector = None
                process.deleteLater()
                if not self.closing and not self.collector_received:
                    self.notify(
                        "sync-error",
                        message="주차학습 연결이 종료됐습니다. 다시 시도하세요.",
                    )
                if self.closing:
                    self.finish_shutdown()

            process.readyReadStandardOutput.connect(read)
            process.readyReadStandardError.connect(
                lambda: logging.warning(
                    "collector: %s",
                    bytes(process.readAllStandardError()).decode("utf-8", "replace")[
                        -4000:
                    ],
                )
            )
            process.finished.connect(finished)
            process.errorOccurred.connect(
                lambda error: (
                    finished() if error == QProcess.ProcessError.FailedToStart else None
                )
            )
            self.notify("sync-progress", message="주차학습 연결 중")
            process.start()

        def start_sync(self, snapshot):
            if self.closing:
                return
            from learning_calendar.worker import SyncTask

            self.task = SyncTask(
                read_cookies(folder / "canvas_session.dpapi"),
                api.store.path,
                self,
                dom_snapshot=snapshot,
            )
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
                process = self.collector
                process.write(b'{"id":0,"method":"quit"}\n')
                QTimer.singleShot(
                    3000, lambda: process.kill() if self.collector is process else None
                )
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
    return code
