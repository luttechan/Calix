"""Bounded stdio input without a blocked Python reader at interpreter exit."""

import json
import os
import sys
from PySide6.QtCore import QObject, QTimer


class StdioInput(QObject):
    def __init__(self, receive, report_error, parent=None):
        super().__init__(parent)
        self.receive = receive
        self.report_error = report_error
        self.buffer = bytearray()
        self.fd = sys.stdin.fileno()
        self.closed = False
        if os.name == "nt":
            import ctypes
            import msvcrt
            from ctypes import wintypes

            self.ctypes = ctypes
            self.wintypes = wintypes
            self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            self.kernel.PeekNamedPipe.argtypes = [
                wintypes.HANDLE,
                ctypes.c_void_p,
                wintypes.DWORD,
                ctypes.c_void_p,
                ctypes.POINTER(wintypes.DWORD),
                ctypes.c_void_p,
            ]
            self.kernel.PeekNamedPipe.restype = wintypes.BOOL
            self.handle = msvcrt.get_osfhandle(self.fd)
        else:
            os.set_blocking(self.fd, False)
        self.timer = QTimer(self)
        self.timer.setInterval(8)
        self.timer.timeout.connect(self.poll)
        self.timer.start()

    def stop(self):
        self.closed = True
        self.timer.stop()

    def eof(self):
        self.stop()
        self.receive(dict(id=0, method="quit", params={}))

    def poll(self):
        if self.closed:
            return
        budget = 256 * 1024
        while budget > 0:
            count = min(budget, 65536)
            if os.name == "nt":
                available = self.wintypes.DWORD()
                if not self.kernel.PeekNamedPipe(
                    self.handle, None, 0, None, self.ctypes.byref(available), None
                ):
                    self.eof()
                    return
                if not available.value:
                    return
                count = min(count, available.value)
            try:
                chunk = os.read(self.fd, count)
            except BlockingIOError:
                return
            except OSError:
                self.eof()
                return
            if not chunk:
                self.eof()
                return
            budget -= len(chunk)
            self.buffer.extend(chunk)
            while b"\n" in self.buffer:
                line, _, rest = self.buffer.partition(b"\n")
                self.buffer = bytearray(rest)
                if len(line) > 2 * 1024 * 1024:
                    self.report_error("요청이 너무 큽니다.")
                    continue
                try:
                    request = json.loads(line)
                    if not isinstance(request, dict):
                        raise ValueError()
                except (ValueError, UnicodeError):
                    self.report_error("요청 형식을 확인하세요.")
                    continue
                self.receive(request)
                if self.closed:
                    return
            if len(self.buffer) > 2 * 1024 * 1024:
                self.report_error("요청이 너무 큽니다.")
                self.eof()
                return
