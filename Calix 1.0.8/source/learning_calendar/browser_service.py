"""Resident Chromium context, controlled through a user-scoped local pipe.

Only state notifications cross the pipe. Cookie snapshots remain DPAPI files.
"""
import json
from pathlib import Path
from PySide6.QtCore import QObject,QTimer
from PySide6.QtNetwork import QLocalSocket
from .cookies import write_cookies,canvas_session_available

class BrowserService(QObject):
    def __init__(self,app,dialog,output,server,parent=None):
        super().__init__(parent);self.app=app;self.dialog=dialog;self.output=Path(output);self.buffer=bytearray();self.closing=False
        self.socket=QLocalSocket(self);self.socket.readyRead.connect(self._read)
        self.socket.disconnected.connect(self.shutdown);self.socket.connected.connect(lambda:self.send('ready'))
        dialog.session_ready.connect(self.authenticated);dialog.session_changed.connect(self.updated)
        dialog.dismissed.connect(lambda:self.send('dismissed'));dialog.logged_out.connect(self.logged_out)
        self.quit_timer=QTimer(self);self.quit_timer.setInterval(50);self.quit_timer.timeout.connect(self._finish_shutdown)
        self.socket.errorOccurred.connect(lambda *_:self.shutdown())
        self.socket.connectToServer(server)
    def send(self,event,**fields):
        if self.socket.state()==QLocalSocket.LocalSocketState.ConnectedState:
            self.socket.write((json.dumps({'event':event,**fields})+'\n').encode('utf-8'));self.socket.flush()
    def _read(self):
        self.buffer.extend(bytes(self.socket.readAll()))
        if len(self.buffer)>16384:self.shutdown();return
        while b'\n' in self.buffer:
            line,_,tail=self.buffer.partition(b'\n');self.buffer=bytearray(tail)
            try:command=json.loads(line).get('command')
            except (ValueError,AttributeError):continue
            if command=='show':self.dialog.show();self.dialog._bring_forward()
            elif command=='authenticate':self.dialog.request_authentication()
            elif command=='logout':self.dialog.request_logout()
            elif command=='quit':self.shutdown()
    def _save(self,rows):
        if not canvas_session_available(rows):return False
        try:write_cookies(self.output,rows);return True
        except OSError:self.send('error',message='세션을 저장하지 못했습니다.');return False
    def authenticated(self,rows):
        if self.closing:return
        if self._save(rows):self.send('authenticated',movies_ready=self.dialog._has_token())
    def updated(self,rows):
        if not self.closing and self._save(rows):self.send('session_updated',movies_ready=self.dialog._has_token())
    def logged_out(self):
        self.output.unlink(missing_ok=True);self.send('logged_out')
    def shutdown(self):
        if self.closing:return
        self.closing=True;self.dialog._shutting_down=True;self.dialog.hide();self.dialog._cancelled=True
        self.dialog.capture_timer.stop();self.dialog.bootstrap_timer.stop();self.dialog.snapshot_timer.stop()
        self.quit_timer.start();self._finish_shutdown()
    def _finish_shutdown(self):
        if self.dialog._validator and self.dialog._validator.isRunning():return
        self.quit_timer.stop();self.app.quit()
