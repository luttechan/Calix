"""Nonblocking update operations with UI state supplied to React."""

import hashlib
import json
import os
import tempfile
from pathlib import Path
from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from learning_calendar.updates import (
    LATEST_API,
    parse_release,
    trusted_download,
    version_key,
    MAX_INSTALLER,
)

VERSION = "1.4.2"


class UpdateService(QObject):
    def __init__(self, notify, parent=None):
        super().__init__(parent)
        self.notify = notify
        self.manager = QNetworkAccessManager(self)
        self.reply = None
        self.release = None
        self.buffer = bytearray()
        self.file = None
        self.partial = None
        self.installer = None
        self.received = 0
        self.redirects = 0
        self.phase = "idle"
        self.state = dict(phase="idle", current=VERSION, message="")
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(20000)
        self.timer.timeout.connect(lambda: self.fail("연결 시간이 초과됐습니다."))

    def publish(self, phase, message="", **extra):
        self.phase = phase
        self.state = dict(phase=phase, current=VERSION, message=message, **extra)
        self.notify("update-state", **self.state)

    def request(self, url):
        request = QNetworkRequest(QUrl(url))
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.ManualRedirectPolicy,
        )
        request.setRawHeader(b"User-Agent", ("Calix/" + VERSION).encode())
        request.setRawHeader(
            b"Accept",
            (
                b"application/vnd.github+json"
                if self.phase == "checking"
                else b"application/octet-stream"
            ),
        )
        request.setTransferTimeout(20000)
        self.reply = self.manager.get(request)
        self.reply.setReadBufferSize(256 * 1024)
        self.reply.readyRead.connect(self.read)
        self.reply.finished.connect(self.finished)
        self.timer.start()

    def check(self):
        self.cancel()
        self.buffer.clear()
        self.publish("checking", "업데이트 확인 중")
        self.request(LATEST_API)

    def download(self):
        if (
            not self.release
            or not self.release.installer_url
            or version_key(self.release.tag) <= version_key(VERSION)
        ):
            raise ValueError("업데이트를 먼저 확인하세요.")
        self.cancel()
        directory = Path(tempfile.mkdtemp(prefix="Calix-update-"))
        self.partial = directory / "setup.part"
        self.file = self.partial.open("xb", buffering=0)
        self.hash = hashlib.sha256()
        self.received = 0
        self.redirects = 0
        self.publish("downloading", "다운로드 중", progress=0, latest=self.release.tag)
        self.request(self.release.installer_url)

    def read(self):
        if not self.reply:
            return
        self.timer.start()
        if (
            self.reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            != 200
        ):
            self.reply.readAll()
            return
        data = bytes(self.reply.readAll())
        if self.phase == "checking":
            if len(self.buffer) + len(data) > 2 * 1024 * 1024:
                self.fail("릴리즈 정보가 너무 큽니다.")
            else:
                self.buffer.extend(data)
            return
        self.received += len(data)
        if self.received > min(MAX_INSTALLER, self.release.size):
            self.fail("설치 파일 크기가 일치하지 않습니다.")
            return
        try:
            if self.file.write(data) != len(data):
                raise OSError("Incomplete update write")
        except OSError:
            self.fail("설치 파일을 저장하지 못했습니다.")
            return
        self.hash.update(data)
        self.publish(
            "downloading",
            "다운로드 중",
            progress=int(self.received * 100 / self.release.size),
            latest=self.release.tag,
        )

    def release_reply(self):
        self.timer.stop()
        reply, self.reply = self.reply, None
        if reply:
            reply.blockSignals(True)
            reply.abort()
            reply.deleteLater()

    def finished(self):
        reply = self.reply
        if not reply:
            return
        self.read()
        if self.reply is not reply:
            return
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        redirect = reply.attribute(QNetworkRequest.Attribute.RedirectionTargetAttribute)
        if (
            self.phase == "downloading"
            and status in (301, 302, 303, 307, 308)
            and redirect
        ):
            target = reply.url().resolved(redirect).toString()
            self.redirects += 1
            self.release_reply()
            if self.redirects > 5 or not trusted_download(target):
                self.fail("다운로드 주소를 확인할 수 없습니다.")
            else:
                self.request(target)
            return
        error = reply.error()
        self.release_reply()
        if status != 200 or error != QNetworkReply.NetworkError.NoError:
            self.fail("업데이트 서버에 연결하지 못했습니다.")
            return
        if self.phase == "checking":
            try:
                self.release = parse_release(json.loads(self.buffer))
            except (ValueError, TypeError):
                self.fail("릴리즈 정보를 확인할 수 없습니다.")
                return
            finally:
                self.buffer.clear()
            if version_key(self.release.tag) <= version_key(VERSION):
                self.publish("current", "최신 버전입니다.")
            elif self.release.installer_url:
                self.publish(
                    "available", "업데이트가 있습니다.", latest=self.release.tag
                )
            else:
                self.publish("manual", "새 버전이 있습니다.", latest=self.release.tag)
            return
        try:
            self.file.flush()
            os.fsync(self.file.fileno())
            self.file.close()
            self.file = None
            if (
                self.received != self.release.size
                or self.hash.hexdigest() != self.release.digest
            ):
                raise ValueError()
            path = self.partial.with_name("Calix-Setup.exe")
            self.partial.replace(path)
            self.partial = None
            self.installer = (str(path), self.release.digest)
        except (OSError, ValueError):
            self.fail("설치 파일 검증에 실패했습니다.")
            return
        self.publish("ready", "설치 준비 완료", latest=self.release.tag, progress=100)

    def fail(self, message):
        self.cancel()
        self.publish("error", message)

    def cancel(self, keep_installer=False):
        self.release_reply()
        if self.file:
            try:
                self.file.close()
            except OSError:
                pass
            self.file = None
        paths = [self.partial]
        self.partial = None
        if self.installer and not keep_installer:
            paths.append(Path(self.installer[0]))
            self.installer = None
        for path in paths:
            if path:
                try:
                    path.unlink(missing_ok=True)
                    path.parent.rmdir()
                except OSError:
                    pass
