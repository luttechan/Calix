"""Nonblocking native update UI with bounded streaming downloads."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from PySide6.QtCore import Qt,QUrl,Signal,QTimer
from PySide6.QtGui import QDesktopServices
from PySide6.QtNetwork import QNetworkAccessManager,QNetworkRequest,QNetworkReply
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QProgressBar
from .design import VERSION
from .updates import LATEST_API,MAX_INSTALLER,RELEASES,parse_release,version_key,trusted_download


class UpdateDialog(QDialog):
    install_requested=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent);self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle('업데이트');self.setMinimumWidth(400)
        layout=QVBoxLayout(self);layout.setContentsMargins(24,24,24,24);layout.setSpacing(16)
        self.caption=QLabel(f'Calix {VERSION}');layout.addWidget(self.caption)
        self.message=QLabel('');self.message.setTextFormat(Qt.TextFormat.PlainText);self.message.setWordWrap(True);layout.addWidget(self.message)
        self.progress=QProgressBar();self.progress.hide();layout.addWidget(self.progress)
        row=QHBoxLayout();self.release_button=QPushButton('릴리즈');self.release_button.clicked.connect(self.open_release);row.addWidget(self.release_button);row.addStretch()
        self.action=QPushButton('다시 확인');self.action.clicked.connect(self.act);row.addWidget(self.action)
        close=QPushButton('닫기');close.clicked.connect(self.close);row.addWidget(close);layout.addLayout(row)
        self.manager=QNetworkAccessManager(self);self.reply=None;self.release=None;self.mode='check'
        self.buffer=bytearray();self.file=None;self.partial=None;self.installer=None;self.redirects=0;self.received=0
        self.timeout=QTimer(self);self.timeout.setSingleShot(True);self.timeout.setInterval(20_000);self.timeout.timeout.connect(lambda:self.fail('연결 시간이 초과됐습니다.'))
        self.initial_check=QTimer(self);self.initial_check.setSingleShot(True);self.initial_check.timeout.connect(self.check)
        self.action.setEnabled(False);self.initial_check.start(0)

    def open_release(self):QDesktopServices.openUrl(QUrl(self.release.url if self.release else RELEASES))

    def act(self):
        if self.mode=='ready':self.install_requested.emit(str(self.installer))
        elif self.mode=='download':self.download()
        else:self.check()

    def request(self,url):
        request=QNetworkRequest(QUrl(url));request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        request.setRawHeader(b'User-Agent',f'Calix/{VERSION}'.encode());request.setRawHeader(b'Accept',b'application/vnd.github+json' if self.mode=='check' else b'application/octet-stream')
        request.setTransferTimeout(20_000)
        self.reply=self.manager.get(request);self.reply.setReadBufferSize(256*1024)
        self.reply.readyRead.connect(self.read);self.reply.finished.connect(self.network_finished)
        self.timeout.start()

    def check(self):
        self.cancel();self.mode='check';self.release=None;self.buffer.clear();self.action.setEnabled(False);self.progress.hide();self.message.setText('업데이트 확인 중')
        self.request(LATEST_API)

    def download(self):
        self.cancel();self.mode='download';self.action.setEnabled(False);self.progress.setRange(0,100);self.progress.setValue(0);self.progress.show();self.message.setText('다운로드 중')
        self.received=0;self.redirects=0;self.hash=hashlib.sha256()
        try:
            # A unique per-user staging directory prevents overwrite of an existing download.
            directory=Path(tempfile.mkdtemp(prefix='Calix-update-'))
            self.partial=directory/'setup.part';self.file=self.partial.open('xb')
            self.request(self.release.installer_url)
        except OSError:self.fail('설치 파일을 저장하지 못했습니다.')

    def read(self):
        if not self.reply:return
        self.timeout.start()
        status=self.reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        if status!=200:
            self.reply.readAll();return
        data=bytes(self.reply.readAll())
        if self.mode=='check':
            if len(self.buffer)+len(data)>2*1024*1024:self.fail('응답 크기가 너무 큽니다.');return
            self.buffer.extend(data)
        else:
            self.received+=len(data)
            if self.received>self.release.size or self.received>MAX_INSTALLER:self.fail('설치 파일 크기가 일치하지 않습니다.');return
            try:self.file.write(data)
            except OSError:self.fail('설치 파일을 저장하지 못했습니다.');return
            self.hash.update(data);self.progress.setValue(int(self.received*100/self.release.size))

    def network_finished(self):
        reply=self.reply
        if reply is None:return
        self.read()
        if self.reply is not reply:return
        self.timeout.stop();status=reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        redirect=reply.attribute(QNetworkRequest.Attribute.RedirectionTargetAttribute)
        if self.mode=='download' and status in (301,302,303,307,308) and redirect:
            url=reply.url().resolved(redirect).toString();self.redirects+=1
            self.release_reply()
            if self.redirects>5 or not trusted_download(url):self.fail('다운로드 주소를 확인할 수 없습니다.');return
            self.request(url);return
        error=reply.error();self.release_reply()
        if status!=200 or error!=QNetworkReply.NetworkError.NoError:
            self.fail('요청 한도를 초과했습니다. 잠시 후 다시 확인하십시오.' if status==403 else '업데이트 서버에 연결하지 못했습니다.');return
        if self.mode=='check':
            try:self.release=parse_release(json.loads(self.buffer))
            except (ValueError,TypeError,KeyError):self.fail('릴리즈 정보를 확인할 수 없습니다.');return
            finally:self.buffer.clear()
            self.action.setEnabled(True)
            if version_key(self.release.tag)<=version_key(VERSION):self.message.setText('최신 버전입니다.');self.action.setText('다시 확인')
            elif self.release.installer_url:
                self.mode='download';self.message.setText(f'{self.release.tag.removeprefix("v")} 업데이트가 있습니다.');self.action.setText('다운로드')
            else:self.message.setText('새 버전이 있습니다. 릴리즈에서 확인하십시오.');self.action.setText('다시 확인')
        else:
            try:
                self.file.flush();os.fsync(self.file.fileno());self.file.close();self.file=None
                if self.received!=self.release.size or self.hash.hexdigest()!=self.release.digest:raise ValueError()
                self.installer=self.partial.with_name('Calix-Setup.exe');self.partial.replace(self.installer);self.partial=None
            except (OSError,ValueError):self.fail('설치 파일 검증에 실패했습니다.');return
            self.mode='ready';self.progress.setValue(100);self.message.setText('설치 준비가 완료됐습니다.');self.action.setText('설치하고 종료');self.action.setEnabled(True)

    def release_reply(self):
        reply=self.reply;self.reply=None
        if reply:
            reply.blockSignals(True);reply.abort();reply.deleteLater()

    def cancel(self):
        self.timeout.stop();self.release_reply()
        if self.file:self.file.close();self.file=None
        if self.partial:
            directory=self.partial.parent;self.partial.unlink(missing_ok=True)
            try:directory.rmdir()
            except OSError:pass
            self.partial=None

    def fail(self,message):
        self.cancel();self.mode='check';self.buffer.clear();self.message.setText(message);self.action.setText('다시 확인');self.action.setEnabled(True);self.progress.hide()

    def cleanup(self):
        self.initial_check.stop()
        self.cancel()
        if self.installer:
            self.installer.unlink(missing_ok=True)
            try:self.installer.parent.rmdir()
            except OSError:pass
            self.installer=None

    def done(self,result):
        self.cleanup();super().done(result)

    def closeEvent(self,event):
        self.cleanup();super().closeEvent(event)
