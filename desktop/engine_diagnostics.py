"""Opt-in, bounded, memory-only crawl diagnostics. No response bodies or credentials."""

import logging
import threading
from collections import deque
from datetime import datetime
from urllib.parse import urlsplit

from engine_logging import SecretSafeFormatter


class Diagnostics(logging.Handler):
    def __init__(self):
        super().__init__()
        self.enabled = False
        self.rows = deque(maxlen=600)
        self.sequence = 0
        self.lock_rows = threading.RLock()
        self.setFormatter(SecretSafeFormatter("%(message)s"))

    def set_enabled(self, enabled):
        with self.lock_rows:
            self.enabled = enabled is True
            self.rows.clear()
        return self.enabled

    def add(self, message):
        with self.lock_rows:
            if not self.enabled:
                return
            record = logging.LogRecord(
                "crawl", logging.INFO, "", 0, str(message)[:4096], (), None
            )
            message = self.format(record)
            self.sequence += 1
            self.rows.append(
                dict(
                    id=self.sequence,
                    time=datetime.now().isoformat(timespec="seconds"),
                    message=message,
                )
            )

    def emit(self, record):
        if self.enabled:
            self.add(self.format(record))

    def read(self, after=0):
        with self.lock_rows:
            return dict(
                enabled=self.enabled, rows=[r for r in self.rows if r["id"] > after]
            )

    def install_http_trace(self):
        # One reversible wrapper for requests, including its worker threads.
        import requests

        original = requests.Session.send
        owner = self

        def send(session, request, **kwargs):
            if not owner.enabled:
                return original(session, request, **kwargs)
            url = urlsplit(request.url)
            target = f"{request.method} {url.hostname}{url.path}"
            owner.add("HTTP 시작 " + target)
            try:
                response = original(session, request, **kwargs)
            except Exception as error:
                owner.add(f"HTTP 실패 {target} {type(error).__name__}")
                raise
            owner.add(f"HTTP 응답 {response.status_code} {target}")
            return response

        requests.Session.send = send
        return lambda: setattr(requests.Session, "send", original)
