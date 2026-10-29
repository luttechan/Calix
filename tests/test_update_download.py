"""Exercise real Qt networking against an isolated loopback server."""
import hashlib,json,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import pytest
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from learning_calendar.updates import Release
from learning_calendar.update_dialog import UpdateDialog

@pytest.fixture(scope='module')
def app():return QApplication.instance() or QApplication([])

def wait(app,condition):
    deadline=time.monotonic()+4
    while time.monotonic()<deadline:
        app.processEvents()
        if condition():return
        time.sleep(.005)
    assert condition(),'Qt operation timed out'

@pytest.fixture
def server():
    from tests.test_release109 import release_payload
    blob=b'MZ'+b'calix installer fixture'*12000
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            if self.path=='/api':body=json.dumps(release_payload(blob)).encode()
            elif self.path=='/redirect':
                self.send_response(302);self.send_header('Location','https://attacker.invalid/setup.exe');self.end_headers();return
            else:body=blob
            self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers()
            try:
                for start in range(0,len(body),4096):self.wfile.write(body[start:start+4096])
            except (BrokenPipeError,ConnectionResetError):pass
    service=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=service.serve_forever,daemon=True);thread.start()
    yield f'http://127.0.0.1:{service.server_port}',blob
    service.shutdown();service.server_close();thread.join(2)

def dialog(app,server,monkeypatch):
    import learning_calendar.update_dialog as module
    base,blob=server;monkeypatch.setattr(module,'LATEST_API',base+'/api')
    widget=UpdateDialog();wait(app,lambda:widget.action.isEnabled())
    assert widget.mode=='download' and '업데이트가 있습니다' in widget.message.text()
    return widget

def cleanup(widget,app):
    widget.close();widget.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()

def test_download_is_streamed_verified_and_removed_on_close(app,server,monkeypatch):
    widget=dialog(app,server,monkeypatch);base,blob=server
    widget.release=Release('v1.0.10','https://github.com/luttechan/Calix/releases/tag/v1.0.10',base+'/setup',hashlib.sha256(blob).hexdigest(),len(blob))
    widget.download();wait(app,lambda:widget.action.isEnabled())
    assert widget.mode=='ready' and widget.progress.value()==100
    path=widget.installer;assert path.read_bytes()==blob
    calls=[];widget.install_requested.connect(calls.append);widget.act();assert calls==[str(path)]
    cleanup(widget,app);assert not path.exists() and not path.parent.exists()

@pytest.mark.parametrize('failure',['digest','size','redirect'])
def test_invalid_downloads_cannot_be_installed(app,server,monkeypatch,failure):
    widget=dialog(app,server,monkeypatch);base,blob=server
    widget.release=Release('v1.0.10','',base+('/redirect' if failure=='redirect' else '/setup'),'0'*64 if failure=='digest' else hashlib.sha256(blob).hexdigest(),len(blob)-1 if failure=='size' else len(blob))
    widget.download();directory=widget.partial.parent;wait(app,lambda:widget.action.isEnabled())
    assert widget.mode=='check' and widget.installer is None and not directory.exists()
    cleanup(widget,app)

def test_cancelled_exit_keeps_download_and_no_installer_is_started(app,tmp_path,monkeypatch):
    from learning_calendar.gui import MainWindow
    widget=MainWindow(tmp_path);monkeypatch.setattr(widget,'_confirm_exit',lambda pending:'cancel')
    widget._install_update(str(tmp_path/'verified.exe'))
    assert not widget._closed and widget._update_installer is None
    widget.dispose();cleanup(widget,app)
