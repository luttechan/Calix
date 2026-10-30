"""Resident Chromium context, controlled through a user-scoped local pipe.

Course snapshots and state notifications cross the pipe. Credentials remain DPAPI files.
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
        self.catalog=None;self.collector=None;self.collecting=False
        self.socket.disconnected.connect(self.shutdown);self.socket.connected.connect(lambda:self.send('ready'))
        dialog.session_ready.connect(self.authenticated);dialog.session_changed.connect(self.updated)
        dialog.dismissed.connect(lambda:self.send('dismissed'));dialog.logged_out.connect(self.logged_out)
        self.quit_timer=QTimer(self);self.quit_timer.setInterval(50);self.quit_timer.timeout.connect(self._finish_shutdown)
        self.socket.errorOccurred.connect(lambda *_:self.shutdown())
        self.socket.connectToServer(server)
    def send(self,event,**fields):
        if self.socket.state()==QLocalSocket.LocalSocketState.ConnectedState:
            payload=(json.dumps({'event':event,**fields},ensure_ascii=False)+'\n').encode('utf-8')
            if len(payload)>3*1024*1024:
                payload=b'{"event":"collection_error","message":"Collection response exceeds size limit."}\n'
            self.socket.write(payload);self.socket.flush()
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
            elif command=='collect':self.collect()
            elif command=='cancel_collection':self.cancel_collection()
            elif command=='quit':self.shutdown()
    def _save(self,rows):
        if not canvas_session_available(rows):return False
        try:write_cookies(self.output,rows);return True
        except OSError:self.send('error',message='세션을 저장하지 못했습니다.');return False
    def authenticated(self,rows):
        if self.closing:return
        if self._save(rows):self.send('authenticated',movies_ready=self.dialog.movies_verified)
    def updated(self,rows):
        if not self.closing and self._save(rows):self.send('session_updated',movies_ready=self.dialog.movies_verified)

    def collect(self):
        if self.closing:return
        if self.collecting or (self.catalog and self.catalog.isRunning()):
            self.send('collection_error',message='주차학습 화면을 읽고 있습니다.');return
        if not self.dialog.profile:
            self.send('collection_error',message='로그인 창이 준비되지 않았습니다.');return
        from .login import LoginValidation
        self.collecting=True;self.catalog=LoginValidation(list(self.dialog.rows.values()),self)
        self.catalog.checked.connect(self._courses_ready)
        self.catalog.failed.connect(self._collection_failed)
        self.catalog.finished.connect(self._catalog_finished);self.catalog.start()

    def _catalog_finished(self):
        task=self.catalog;self.catalog=None
        if task:task.deleteLater()

    def _courses_ready(self,result):
        if self.closing or not self.collecting:return
        from .dom_collector import ScreenCollector
        self.collector=ScreenCollector(self.dialog.profile,result['owner'],result['courses'],self)
        self.collector.progress.connect(lambda message:self.send('collection_progress',message=message))
        self.collector.finished.connect(self._collected);self.collector.start()

    def _collected(self,result):
        if self.closing or not self.collecting:return
        self.collecting=False
        collector=self.collector;self.collector=None
        if collector:collector.deleteLater()
        self.send('videos_collected',snapshot=result)

    def _collection_failed(self,message):
        if not self.collecting:return
        self.collecting=False
        if not self.closing:self.send('collection_auth_required' if '만료' in message else 'collection_error',message=message)

    def cancel_collection(self):
        self.collecting=False
        if self.collector:self.collector.cancel();self.collector.deleteLater();self.collector=None
    def logged_out(self):
        self.cancel_collection()
        self.output.unlink(missing_ok=True);self.send('logged_out')
    def shutdown(self):
        if self.closing:return
        self.closing=True;self.dialog._shutting_down=True;self.dialog.hide();self.dialog._cancelled=True
        self.cancel_collection()
        self.dialog.capture_timer.stop();self.dialog.bootstrap_timer.stop();self.dialog.snapshot_timer.stop()
        self.quit_timer.start();self._finish_shutdown()
    def _finish_shutdown(self):
        if self.dialog._validator and self.dialog._validator.isRunning():return
        if self.catalog and self.catalog.isRunning():return
        self.quit_timer.stop();self.app.quit()
