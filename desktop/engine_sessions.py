"""School session exchange for the trusted local WebView2 login window."""

import base64
import threading
import time
from queue import Queue, Empty
from PySide6.QtCore import QDateTime, QThread, Signal
from PySide6.QtNetwork import QNetworkCookie
from learning_calendar.cookies import (
    campus_domain,
    cookie_record,
    canvas_session_available,
)


def import_cookie_records(values):
    if not isinstance(values, list) or not 0 < len(values) <= 512:
        raise ValueError("학교 로그인 후 완료를 누르세요.")
    result = []
    for value in values:
        if not isinstance(value, dict):
            raise ValueError("로그인 정보를 확인하세요.")
        name, content, domain = (value.get(key) for key in ("name", "value", "domain"))
        if not all(isinstance(item, str) for item in (name, content, domain)):
            raise ValueError("로그인 정보를 확인하세요.")
        if not campus_domain(domain):
            continue
        if not name or len(name) > 512 or len(content) > 65536:
            raise ValueError("로그인 정보를 확인하세요.")
        cookie = QNetworkCookie(name.encode(), content.encode())
        cookie.setDomain(domain)
        path = value.get("path", "/")
        if not isinstance(path, str) or not path.startswith("/") or len(path) > 2048:
            raise ValueError("로그인 정보를 확인하세요.")
        cookie.setPath(path)
        cookie.setSecure(bool(value.get("secure", True)))
        cookie.setHttpOnly(bool(value.get("httpOnly", False)))
        expires = value.get("expires")
        if type(expires) is int:
            cookie.setExpirationDate(QDateTime.fromSecsSinceEpoch(expires))
        record = cookie_record(cookie)
        if record:
            result.append(record)
    if not canvas_session_available(result):
        raise ValueError("학교 로그인 후 완료를 누르세요.")
    return result


class SessionValidation(QThread):
    checked = Signal(object)
    failed = Signal(str)

    def __init__(self, cookies, parent=None):
        super().__init__(parent)
        self.cookies = cookies
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()

    def run(self):
        from learning_calendar.sync import CampusClient, AuthenticationRequired

        result = Queue(maxsize=1)
        rows, cancelled = self.cookies, self.cancel_event

        def fetch():
            client = CampusClient(rows, cancelled)
            try:
                identity = client._get("/api/v1/users/self/profile").json()
                identifier = identity.get("id") if isinstance(identity, dict) else None
                if isinstance(identifier, bool) or not 0 < int(identifier) < 2**63:
                    raise ValueError()
                courses = client._list_courses()
                if not courses:
                    raise ValueError()
                result.put(
                    (
                        True,
                        dict(
                            owner=str(identifier),
                            courses=[dict(id=c.id, name=c.name) for c in courses],
                        ),
                    )
                )
            except AuthenticationRequired:
                result.put((False, "학교 로그인 후 다시 완료를 누르세요."))
            except Exception:
                result.put((False, "학교 연결을 확인하지 못했습니다. 다시 시도하세요."))
            finally:
                client.session.close()

        network = threading.Thread(target=fetch, daemon=True)
        network.start()
        deadline = time.monotonic() + 90
        try:
            while not cancelled.is_set():
                try:
                    valid, value = result.get(timeout=0.025)
                except Empty:
                    if time.monotonic() >= deadline:
                        cancelled.set()
                        self.failed.emit("학교 연결 시간이 초과됐습니다.")
                        return
                    continue
                if not cancelled.is_set():
                    if valid:
                        self.checked.emit(value)
                    else:
                        self.failed.emit(value)
                return
        finally:
            self.cookies = []
