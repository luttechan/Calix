import json
import sqlite3
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import pytest
import requests
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from learning_calendar.gui import MainWindow
from learning_calendar.models import Course,Event
from learning_calendar.snapshot import Snapshot
from learning_calendar.storage import Store


@pytest.fixture(scope='module')
def app():return QApplication.instance() or QApplication([])


def dispose(w,app):
    w.dispose();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()


def result(path):
    return dict(path=str(path),snapshot=Snapshot(),sessions=[],last_sync='',warnings=[],stats={'new':0,'updated':0})


def test_session_write_failure_keeps_existing_session_and_unblocks_ui(app,tmp_path,monkeypatch):
    import learning_calendar.cookies as cookies
    w=MainWindow(tmp_path);w.session_path.write_bytes(b'previous protected session');w._login_output=tmp_path/'child.dpapi'
    monkeypatch.setattr(cookies,'read_cookies',lambda *_:[{'domain':'canvas.bufs.ac.kr','name':'session','value':'synthetic'}])
    monkeypatch.setattr(cookies,'write_cookies',lambda *_:(_ for _ in ()).throw(PermissionError('locked')))
    w._set_busy(True);w._browser_event({'event':'authenticated'})
    assert not w._busy and not w._logged_in and w.status.text()=='로그인 세션 저장 실패'
    assert w.session_path.read_bytes()==b'previous protected session'
    dispose(w,app)


def test_failed_logout_does_not_disable_future_login_events(app,tmp_path,monkeypatch):
    w=MainWindow(tmp_path);w.session_path.write_bytes(b'protected session');w._set_logged_in(True)
    unlink=Path.unlink
    def locked(path,*args,**kwargs):
        if path==w.session_path:raise PermissionError('locked')
        return unlink(path,*args,**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path,'unlink',locked);w.logout()
    assert w._logged_in and not w._logging_out and not w._busy and w.session_path.exists()
    w.logout();assert not w._logged_in and not w.session_path.exists()
    dispose(w,app)


def test_account_database_open_failure_preserves_working_store(app,tmp_path,monkeypatch):
    import learning_calendar.gui as gui
    w=MainWindow(tmp_path);old=w.store
    old.apply_batch([Course(1,'Previous')],{(1,'movie'):[Event('movie:1:1',1,'Previous','movie','Keep',None,False)]})
    monkeypatch.setattr(gui,'Store',lambda *_:(_ for _ in ()).throw(sqlite3.DatabaseError('unreadable')))
    w._sync_ok(result(tmp_path/'new-account.db'))
    assert w.store is old and old.events()[0].title=='Keep'
    assert w.status.text()=='계정 일정 열기 실패'
    dispose(w,app)


def test_account_settings_write_failure_still_shows_correct_account_data(app,tmp_path,monkeypatch):
    import learning_calendar.gui as gui
    path=tmp_path/'new-account.db';new=Store(path);event=Event('movie:2:1',2,'New account','movie','New data',None,False)
    new.apply_batch([Course(2,'New account')],{(2,'movie'):[event]});new.close()
    w=MainWindow(tmp_path);payload=result(path);payload['snapshot']=Snapshot([event],[Course(2,'New account')])
    monkeypatch.setattr(gui,'write_settings',lambda *_:(_ for _ in ()).throw(PermissionError('locked')))
    w._sync_ok(payload)
    assert w.store.path==path and w.snapshot.events[0].title=='New data'
    assert w.store.events()[0].title=='New data' and '설정 저장 실패' in w.status.text()
    dispose(w,app)


def test_sync_error_dialog_is_nonblocking_and_old_close_cannot_remove_new_dialog(app,tmp_path):
    w=MainWindow(tmp_path);w._sync_failed('first failure');first=w._dialogs['sync_result']
    w._sync_failed('second failure');assert w._dialogs['sync_result'] is first
    assert first.detailedText()=='second failure'
    first.done(0);w._sync_failed('third failure');second=w._dialogs['sync_result']
    assert second is not first
    QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
    assert w._dialogs['sync_result'] is second and second.detailedText()=='third failure'
    dispose(w,app)


def test_login_ready_timeout_releases_busy_state(app,tmp_path):
    w=MainWindow(tmp_path);calls=[];w._login_ready=tmp_path/'not-created.ready'
    w._login_ready_deadline=time.monotonic()-1;w._login_process=SimpleNamespace(kill=lambda:calls.append('kill'))
    w._set_busy(True);w._check_login_ready()
    assert calls==['kill'] and not w._busy and not w._login_then_sync and w._login_timed_out
    w._login_process=None;dispose(w,app)


def test_undeletable_login_temp_does_not_break_process_cleanup(app,tmp_path,monkeypatch):
    w=MainWindow(tmp_path);w._login_output=tmp_path/'login.dpapi';w._login_output.write_bytes(b'fixture')
    calls=[];w._login_process=SimpleNamespace(deleteLater=lambda:calls.append('deleted'))
    unlink=Path.unlink
    def locked(path,*args,**kwargs):
        if path==w._login_output:raise PermissionError('locked')
        return unlink(path,*args,**kwargs)
    monkeypatch.setattr(Path,'unlink',locked);w._set_busy(True);w._finish_login(False,'ended')
    assert calls==['deleted'] and not w._busy and w._login_process is None
    dispose(w,app)


@pytest.mark.parametrize('temporary_failure',[False,True])
def test_full_gui_sync_http_storage_and_restart(app,tmp_path,monkeypatch,temporary_failure):
    import learning_calendar.cookies as cookies
    import learning_calendar.sync as sync
    attempts={};lock=threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            path=urlsplit(self.path).path
            with lock:attempts[path]=attempts.get(path,0)+1;attempt=attempts[path]
            status=200
            if path.endswith('/profile'):body={'id':1}
            elif path=='/api/v1/courses':body=[{'id':1,'name':'Course 1'},{'id':2,'name':'Course 2'}]
            elif path.endswith('/modules'):
                cid=int(path.split('/')[-2])
                if temporary_failure and cid==2 and attempt==1:status=503;body={}
                else:body=[{'title':'Week 1','module_items':[{'completed':i==1,'content_data':{'item_id':i,'title':f'Video {i}','due_at':'2088-01-02T14:59:59Z','item_content_data':{'content_type':'movie'}}} for i in (1,2)]}]
            elif path.endswith('/assignments'):
                cid=int(path.split('/')[-2]);body=[{'id':1,'name':f'Task {cid}','due_at':'2088-01-03T14:59:59Z','submission':{'workflow_state':'unsubmitted'}}]
            else:status=404;body={}
            raw=json.dumps(body).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    get=requests.Session.get;base=f'http://127.0.0.1:{server.server_port}'
    def transport(self,url,*args,**kwargs):return get(self,base+urlsplit(url).path,*args,**kwargs)
    monkeypatch.setattr(requests.Session,'get',transport)
    rows=[{'domain':'canvas.bufs.ac.kr','name':'_normandy_session','value':'synthetic','path':'/'},
          {'domain':'canvas.bufs.ac.kr','name':'xn_api_token','value':'synthetic','path':'/'}]
    monkeypatch.setattr(cookies,'read_cookies',lambda *_:rows)
    w=MainWindow(tmp_path)
    try:
        w.manual_sync();deadline=time.monotonic()+8
        while w._thread is not None and time.monotonic()<deadline:app.processEvents();time.sleep(.005)
        assert w._thread is None and not w._busy and not w.partial and not w._dialogs
        assert len(w.snapshot.events)==6 and len(w.store.events())==6 and w._logged_in
        assert len(w.snapshot.by_kind['movie'])==4 and len(w.snapshot.by_kind['assignment'])==2
        w.store.set_note('movie:1:1','Keep note');w.manual_sync()
        while w._thread is not None and time.monotonic()<deadline:app.processEvents();time.sleep(.005)
        assert w._thread is None and len(w.store.events())==6
        assert next(e for e in w.store.events() if e.key=='movie:1:1').note=='Keep note'
        dispose(w,app);w=MainWindow(tmp_path)
        assert len(w.snapshot.events)==6 and next(e for e in w.snapshot.events if e.key=='movie:1:1').note=='Keep note'
    finally:
        if w._thread:w._thread.cancel();w._thread.wait(1000);app.processEvents()
        dispose(w,app);server.shutdown();server.server_close();thread.join(1)


def test_locked_update_download_does_not_crash_or_create_more_downloads(app,tmp_path,monkeypatch):
    from learning_calendar.update_dialog import UpdateDialog
    dialog=UpdateDialog();dialog.initial_check.stop();folder=tmp_path/'owned';folder.mkdir();path=folder/'setup.part'
    path.write_bytes(b'fixture');dialog.partial=path
    unlink=Path.unlink;requests_seen=[]
    def locked(target,*args,**kwargs):
        if target==path:raise PermissionError('locked')
        return unlink(target,*args,**kwargs)
    monkeypatch.setattr(Path,'unlink',locked);monkeypatch.setattr(dialog,'request',requests_seen.append)
    dialog.download()
    assert not requests_seen and dialog.partial==path and dialog.mode=='check' and dialog.action.isEnabled()
    dialog.cleanup();dialog.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()


@pytest.mark.parametrize('broken',[
    {'window_width':None},{'window_height':'not a number'},{'window_width':[]},
    {'theme':{}},{'theme':['dark']},{'glass':'false'},
    {'active_db':'CON.db'},{'active_db':'../another.db'},{'active_db':'bad\x00.db'},
])
def test_malformed_settings_do_not_prevent_launch(app,tmp_path,broken):
    (tmp_path/'settings.json').write_text(json.dumps(broken),encoding='utf-8')
    w=MainWindow(tmp_path)
    assert w.width()>0 and w.height()>0 and isinstance(w.theme_key,str)
    assert w.store.path.name=='learning.db'
    dispose(w,app)
