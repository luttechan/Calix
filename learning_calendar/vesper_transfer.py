"""Short-lived, user-approved encrypted sessions on the local network."""

import base64
from http.server import BaseHTTPRequestHandler, HTTPServer
import ipaddress
import json
import os
import re
import secrets
import socket
from threading import Lock, Thread, Timer
import time
from urllib.parse import urlencode

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


LIFETIME = 300
LIMIT = 8 * 1024 * 1024
NETWORKS = tuple(ipaddress.ip_network(value) for value in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16",
))


def local_address(host):
    try:
        address = ipaddress.IPv4Address(host)
        return any(address in network for network in NETWORKS)
    except (ValueError, TypeError):
        return False


def addresses():
    try:
        found = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        return []
    candidates = {row[4][0] for row in found}
    return sorted(filter(local_address, candidates))


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        self.request.settimeout(2)
        self.server.session.active_socket = self.request
        super().setup()

    def finish(self):
        self.server.session.active_socket = None
        super().finish()

    def log_message(self, *_):
        pass

    def do_POST(self):
        session = self.server.session
        if self.path not in ("/offer", "/result", "/received"):
            self.send_error(404)
            return
        try:
            if not local_address(self.client_address[0]) or self.headers.get_all("Host") != [session.authority]:
                raise ValueError()
            lengths = self.headers.get_all("Content-Length") or []
            if (self.headers.get("Transfer-Encoding") or self.headers.get("Content-Type") != "application/octet-stream"
                    or len(lengths) != 1 or not re.fullmatch(r"[0-9]{1,8}", lengths[0])):
                raise ValueError()
            length = int(lengths[0])
            if not 28 < length <= LIMIT + 28:
                raise ValueError()
            # A sender cannot keep an expired listener occupied with partial data.
            payload = bytearray()
            while len(payload) < length:
                if session.expired():
                    raise ValueError()
                chunk = self.rfile.read1(min(64 * 1024, length - len(payload)))
                if not chunk:
                    raise ValueError()
                payload.extend(chunk)
            status, value = session.exchange(self.path[1:], bytes(payload))
        except (OSError, ValueError, InvalidTag, RecursionError):
            self.send_error(400)
            return
        self.send_response(status)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(value)))
        self.end_headers()
        try:
            self.wfile.write(value)
            self.wfile.flush()
        except OSError:
            return
        if status == 200 and self.path == "/received":
            session.close()


class Transfer:
    def __init__(self, host, computer):
        if not local_address(host):
            raise ValueError("같은 Wi-Fi에 연결한 뒤 다시 시도하세요.")
        self.host = host
        self.computer = computer
        self.secret = secrets.token_bytes(32)
        self.crypto = AESGCM(self.secret)
        self.deadline = time.monotonic() + LIFETIME
        self.expires = int(time.time()) + LIFETIME
        self.guard = Lock()
        self.phase = "waiting"
        self.offer = None
        self.result = None
        self.active_socket = None
        self.server = HTTPServer((host, 0), Handler)
        self.authority = f"{host}:{self.server.server_port}"
        self.server.session = self
        Thread(target=self.server.serve_forever, kwargs={"poll_interval": .2}, daemon=True).start()
        self.timer = Timer(LIFETIME, self.close)
        self.timer.daemon = True
        self.timer.start()

    def code(self):
        from qrcodegen import QrCode

        query = urlencode(dict(v=3, host=self.host, port=self.server.server_port,
                               computer=self.computer, expires=self.expires,
                               key=base64.urlsafe_b64encode(self.secret).decode().rstrip("=")))
        uri = f"calix-vesper://pair?{query}"
        qr = QrCode.encode_text(uri, QrCode.Ecc.MEDIUM)
        size = qr.get_size()
        return dict(expiresAt=self.expires * 1000, uri=uri, rows=[
            "".join("1" if qr.get_module(x, y) else "0" for x in range(size)) for y in range(size)
        ])

    def expired(self):
        return time.monotonic() >= self.deadline or self.phase == "closed"

    def _sealed(self, kind, value):
        raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
        if len(raw) > LIMIT:
            raise ValueError("동기화 용량 한도를 초과했습니다.")
        nonce = os.urandom(12)
        return nonce + self.crypto.encrypt(nonce, raw, f"calix-vesper-v3:{kind}".encode())

    def exchange(self, route, data):
        with self.guard:
            if self.expired():
                return 410, b""
            crypto = self.crypto
        raw = crypto.decrypt(data[:12], data[12:], f"calix-vesper-v3:{route}".encode())
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError()
        with self.guard:
            if self.expired():
                return 410, b""
            receipt = value.get("receipt")
            if not isinstance(receipt, str) or not re.fullmatch(r"[a-f0-9]{32}", receipt):
                raise ValueError()
            if route == "offer":
                name = value.get("name")
                if not isinstance(name, str) or not name.strip() or len(name) > 80 or not name.isprintable():
                    raise ValueError()
                if self.offer and self.offer["receipt"] != receipt:
                    return 409, b""
                if self.phase == "waiting":
                    self.offer = value
                    self.phase = "approval"
                return 200, self._sealed("reply", {"receipt": receipt, "phase": self.phase})
            if not self.offer or self.offer["receipt"] != receipt:
                return 404, b""
            if route == "received":
                if self.phase != "complete":
                    return 409, b""
                return 200, self._sealed("reply", {"receipt": receipt, "phase": "received"})
            return 200, self._sealed("reply", {
                "receipt": receipt, "phase": self.phase,
                **({"snapshot": self.result} if self.phase == "complete" else {}),
            })

    def status(self):
        with self.guard:
            if self.expired():
                return {"phase": "closed"}
            if self.phase == "approval":
                return {"phase": "approval", "name": self.offer["name"], "code": self.offer["receipt"][:6].upper()}
            return {"phase": self.phase}

    def approve(self, apply):
        with self.guard:
            if self.expired() or self.phase != "approval":
                raise ValueError("연동 요청이 만료되었습니다.")
            result = apply(self.offer)
            self.result = result
            self.phase = "complete"
            self.deadline = min(self.deadline, time.monotonic() + 45)
            self.timer.cancel()
            self.timer = Timer(max(0, self.deadline - time.monotonic()), self.close)
            self.timer.daemon = True
            self.timer.start()
            return {"phase": self.phase, "conflicts": len(result["conflicts"])}

    def close(self):
        with self.guard:
            if self.phase == "closed":
                return
            self.phase = "closed"
            self.offer = None
            self.result = None
            self.secret = b""
            self.crypto = None
        self.timer.cancel()
        Thread(target=self._stop, daemon=True).start()

    def _stop(self):
        connection = self.active_socket
        if connection is not None:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self.server.shutdown()
        self.server.server_close()
