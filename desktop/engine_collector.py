"""Invisible browser adapter. The course collector and extraction algorithm stay unchanged."""

import base64
import json
import sys
import time
from pathlib import Path


def run(folder):
    from PySide6.QtCore import (
        QCoreApplication,
        QEvent,
        QTimer,
        QUrl,
        Qt,
        QTemporaryDir,
        QDir,
        Signal,
    )

    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    from PySide6.QtWidgets import QApplication
    from PySide6.QtWebEngineCore import (
        QWebEngineProfile,
        QWebEngineUrlRequestInterceptor,
    )
    from PySide6.QtNetwork import QNetworkCookie
    from learning_calendar.cookies import (
        read_cookies,
        cookie_record,
        canvas_session_available,
        write_cookies,
    )
    from engine_sessions import SessionValidation
    from learning_calendar.dom_collector import ScreenCollector

    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    rows = read_cookies(Path(folder) / "canvas_session.dpapi")
    if not canvas_session_available(rows):
        print(
            json.dumps(
                dict(event="collection_auth_required", message="다시 로그인하세요.")
            ),
            flush=True,
        )
        return 2
    temporary = QTemporaryDir(QDir.tempPath() + "/Calix-collector-XXXXXX")
    if not temporary.isValid():
        raise RuntimeError("주차학습 저장소를 준비하지 못했습니다.")
    profile = QWebEngineProfile("Calix-collector")
    profile.setPersistentStoragePath(temporary.path() + "/storage")
    profile.setCachePath(temporary.path() + "/cache")
    profile.setPersistentCookiesPolicy(
        QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies
    )
    profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
    profile.setHttpCacheMaximumSize(16 * 1024 * 1024)
    store = profile.cookieStore()
    captured = {}

    class TokenInterceptor(QWebEngineUrlRequestInterceptor):
        captured_token = Signal(str)

        def interceptRequest(self, info):
            url = info.requestUrl()
            if (
                url.scheme() != "https"
                or url.host() != "canvas.bufs.ac.kr"
                or not url.path().startswith("/learningx/")
            ):
                return
            for key, value in info.httpHeaders().items():
                if bytes(key).lower() == b"authorization":
                    header = bytes(value).decode("latin1")
                    if header.lower().startswith("bearer "):
                        self.captured_token.emit(header[7:].strip())

    def token_captured(token):
        if not token or len(token) > 65536:
            return
        cookie = QNetworkCookie(b"xn_api_token", token.encode("utf-8"))
        cookie.setDomain("canvas.bufs.ac.kr")
        cookie.setPath("/")
        cookie.setSecure(True)
        cookie.setHttpOnly(True)
        record = cookie_record(cookie)
        if record:
            captured[(record["domain"], record["name"], record["path"])] = record

    interceptor = TokenInterceptor(profile)
    interceptor.captured_token.connect(token_captured)
    profile.setUrlRequestInterceptor(interceptor)
    required = {
        r["name"]
        for r in rows
        if r["domain"].lstrip(".") in ("canvas.bufs.ac.kr", "bufs.ac.kr")
        and "session" in r["name"].lower()
    }
    accepted = set()
    validator = None
    collector = None
    finished = False

    def emit(event, **value):
        print(
            json.dumps(
                dict(event=event, **value), ensure_ascii=False, separators=(",", ":")
            ),
            flush=True,
        )

    def fail(message):
        nonlocal finished
        if finished:
            return
        finished = True
        emit(
            "collection_auth_required" if "로그인" in message else "collection_error",
            message=message,
        )
        if collector:
            collector.cancel()
        if not validator or not validator.isRunning():
            app.quit()

    def added(cookie):
        record = cookie_record(cookie)
        if record:
            captured[(record["domain"], record["name"], record["path"])] = record
            if record["name"] in required:
                accepted.add(record["name"])

    store.cookieAdded.connect(added)
    for row in rows:
        for cookie in QNetworkCookie.parseCookies(base64.b64decode(row["raw"])):
            origin = QUrl("https://" + row["domain"].lstrip(".") + "/")
            if not row["domain"].startswith("."):
                cookie.setDomain("")
            store.setCookie(cookie, origin)

    def collected(snapshot):
        nonlocal finished
        if finished:
            return
        finished = True
        combined = {(r["domain"], r["name"], r["path"]): r for r in rows}
        combined.update(captured)
        write_cookies(Path(folder) / "canvas_session.dpapi", combined.values())
        emit("videos_collected", snapshot=snapshot)
        app.quit()

    def validated(identity):
        nonlocal collector
        if finished:
            return
        collector = ScreenCollector(profile, identity["owner"], identity["courses"])
        collector.progress.connect(
            lambda message: emit("collection_progress", message=message)
        )
        collector.finished.connect(collected)
        collector.start()

    def validation_finished():
        if finished:
            app.quit()

    def begin():
        nonlocal validator
        if not required.issubset(accepted):
            fail("로그인 쿠키를 불러오지 못했습니다. 다시 로그인하세요.")
            return
        validator = SessionValidation(rows)
        validator.checked.connect(validated)
        validator.failed.connect(fail)
        validator.finished.connect(validation_finished)
        validator.start()

    from engine_transport import StdioInput

    def cancel(_request=None):
        nonlocal finished
        finished = True
        if collector:
            collector.cancel()
        if validator:
            validator.cancel()
        app.quit()

    incoming = StdioInput(cancel, lambda _message: None, app)
    retries = 0

    def wait_cookies():
        nonlocal retries
        if finished:
            return
        if required.issubset(accepted) or retries >= 100:
            begin()
        else:
            retries += 1
            QTimer.singleShot(25, wait_cookies)

    emit("collection_progress", message="주차학습 연결 중")
    QTimer.singleShot(0, wait_cookies)
    app.exec()
    incoming.stop()
    if collector:
        collector.cancel()
    if validator and validator.isRunning():
        validator.wait(30000)
    profile.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    temporary.remove()
    return 0 if finished else 2
