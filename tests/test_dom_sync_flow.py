from types import SimpleNamespace
import pytest
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from learning_calendar.gui import MainWindow


@pytest.fixture
def window(tmp_path,monkeypatch):
    import learning_calendar.cookies as cookies
    app=QApplication.instance() or QApplication([])
    w=MainWindow(tmp_path)
    monkeypatch.setattr(cookies,'read_cookies',lambda *_:[{'domain':'canvas.bufs.ac.kr','name':'session','value':'synthetic'}])
    yield w
    w._login_process=None;w._login_socket=None
    w.dispose();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()


def test_sync_requests_rendered_pages_without_video_token(window,monkeypatch):
    commands=[];w=window;w._login_process=object()
    monkeypatch.setattr(w,'_browser_command',lambda command:commands.append(command) or True)
    w.manual_sync()
    assert commands==['collect'] and w._dom_collecting and w._busy and w.collection_timer.isActive()
    started=[]
    monkeypatch.setattr(w,'manual_sync',lambda **kwargs:started.append(kwargs))
    snapshot={'owner':'1','courses':[{'id':1,'name':'Course'}],'results':[]}
    w._browser_event({'event':'videos_collected','snapshot':snapshot})
    assert started==[{'auto':True,'dom_snapshot':snapshot}]
    assert not w._busy and not w._dom_collecting and not w.collection_timer.isActive()


def test_timeout_rejects_late_results(window,monkeypatch):
    w=window;commands=[];started=[];w._dom_collecting=True;w._set_busy(True)
    monkeypatch.setattr(w,'_browser_command',lambda command:commands.append(command))
    monkeypatch.setattr(w,'manual_sync',lambda **kwargs:started.append(kwargs))
    w._collection_timeout();w._browser_event({'event':'videos_collected','snapshot':{'results':[]}})
    assert commands==['cancel_collection'] and not w._busy and not started


def test_dead_browser_clears_pending_collection(window):
    w=window;w._login_process=SimpleNamespace(deleteLater=lambda:None)
    w._login_output=w.appdir/'absent.dpapi';w._dom_collecting=True;w.collection_timer.start();w._set_busy(True)
    w._finish_login(False,'Disconnected')
    assert not w._busy and not w._dom_collecting and not w.collection_timer.isActive()
    assert '수집 연결' in w.status.text()


def test_malformed_snapshot_does_not_start_worker(window,monkeypatch):
    w=window;w._dom_collecting=True;w._set_busy(True);failures=[]
    monkeypatch.setattr(w,'_sync_failed',failures.append)
    w._browser_event({'event':'videos_collected','snapshot':{'results':None}})
    assert failures and w._thread is None and not w._busy
