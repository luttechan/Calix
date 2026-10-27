from datetime import datetime,timedelta
from types import SimpleNamespace
import time
import pytest
from PySide6.QtCore import QCoreApplication,QEvent,QUrl,Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtNetwork import QNetworkCookie
from learning_calendar.login import CampusLoginDialog,learningx_entry,LoginValidation
from learning_calendar.cookies import cookie_record,write_cookies
from learning_calendar.models import Event,KST
from learning_calendar.snapshot import Snapshot
from learning_calendar.gui import MainWindow

@pytest.fixture(scope='module')
def app():return QApplication.instance() or QApplication([])

def dispose(w,app):
    w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()

def session_row():
    cookie=QNetworkCookie(b'_normandy_session',b'synthetic-test-session');cookie.setDomain('canvas.bufs.ac.kr');cookie.setPath('/');cookie.setSecure(True)
    return cookie_record(cookie)

def test_learningx_tab_discovery_limits_to_actual_school_navigation():
    assert learningx_entry([{'label':'주차학습','html_url':'/courses/1/external_tools/7'}])=='https://canvas.bufs.ac.kr/courses/1/external_tools/7'
    assert learningx_entry([{'label':'주차학습','html_url':'https://evil.example/external_tools/7'}]) is None
    assert learningx_entry([{'label':'주차학습','html_url':'/courses/1/external_tools/7','hidden':True}]) is None
    assert learningx_entry([{'label':'학습콘텐츠','html_url':'javascript:alert(1)'}]) is None

def test_bootstrap_opens_discovered_weekly_learning_without_user_click(app):
    d=CampusLoginDialog();d._browser_started=True;urls=[]
    d.view=SimpleNamespace(setUrl=lambda u:urls.append(u.toString()),stop=lambda:None,deleteLater=lambda:None)
    entry='https://canvas.bufs.ac.kr/courses/1/external_tools/7'
    d._checked({'course_id':1,'token_valid':False,'learningx_url':entry})
    assert urls==[entry] and d.bootstrap_timer.isActive() and d._bootstrap_deadline>time.monotonic()+20
    assert '자동' in d.message.text() and '열면' not in d.message.text()
    d.dispose();d.deleteLater();app.processEvents()

def test_navigation_discovery_tries_another_course_when_first_has_no_weekly_tab(app,monkeypatch):
    import learning_calendar.sync as sync
    class Client:
        _learningx_token=None
        session=SimpleNamespace(close=lambda:None)
        def __init__(self,*args):pass
        def _get(self,path):
            data=({'id':3} if path.endswith('/profile') else [{'id':1},{'id':2}] if path.endswith('/dashboard_cards') else
                  [] if '/courses/1/tabs' in path else [{'label':'주차학습','html_url':'/courses/2/external_tools/9'}])
            return SimpleNamespace(json=lambda:data)
    monkeypatch.setattr(sync,'CampusClient',Client)
    task=LoginValidation([]);results=[];task.checked.connect(results.append);task.run()
    assert results[0]['course_id']==2 and results[0]['learningx_url'].endswith('/courses/2/external_tools/9')

def test_repeated_token_events_do_not_restart_cookie_capture_deadline(app):
    d=CampusLoginDialog();d._browser_started=True;d.view=object();d.cookie_store=SimpleNamespace(loadAllCookies=lambda:None)
    d.accept_after_cookie_capture();deadline=d._capture_deadline
    d.accept_after_cookie_capture();assert d._capture_deadline==deadline
    d.view=None;d.dispose();d.deleteLater();app.processEvents()

def test_resident_login_completion_hides_but_keeps_the_same_browser(app):
    d=CampusLoginDialog(resident=True);d._browser_started=True;profile=object();d.profile=profile
    row=session_row();d.rows[d._key(row)]=row;d._validated=True;d._pending_accept=True
    ready=[];d.session_ready.connect(ready.append);d._complete()
    assert d.authenticated and not d.isVisible() and d.profile is profile and ready==[[row]]
    assert d.result()!=1
    d.profile=None;d.dispose();d.deleteLater();app.processEvents()

def test_authentication_changes_button_and_keeps_process_until_explicit_logout(app,tmp_path):
    w=MainWindow(tmp_path);w._login_output=tmp_path/'browser.dpapi';write_cookies(w._login_output,[session_row()])
    process=object();w._login_process=process;w._set_busy(True)
    w._browser_event({'event':'authenticated','movies_ready':True})
    assert w.login_button.text()=='로그아웃' and w._login_process is process and not w._busy
    assert w.session_path.exists() and w._login_output.exists()
    commands=[];w._browser_command=lambda command:commands.append(command)
    w.logout();assert commands==['logout'] and not w.session_path.exists() and w._login_process is process
    w._browser_event({'event':'logged_out'});assert w.login_button.text()=='로그인' and not w._busy
    w._login_process=None;dispose(w,app)

def test_today_categories_and_remaining_table_share_nonexpired_snapshot(app,tmp_path):
    now=datetime(2026,10,26,12,tzinfo=KST)
    rows=[Event('a',1,'기업가정신','assignment','기업가정신 글쓰기',(now+timedelta(days=3)).isoformat(),False),
          Event('b',1,'기업가정신','assignment','오늘 보고서',(now+timedelta(hours=1)).isoformat(),False),
          Event('c',2,'일본어','movie','오늘 영상',(now+timedelta(hours=2)).isoformat(),False),
          Event('old',1,'기업가정신','assignment','지난 과제',(now-timedelta(days=1)).isoformat(),False)]
    w=MainWindow(tmp_path);w.home.update_snapshot(Snapshot(rows),now)
    w.home.set_category('movie');assert [e.key for e in w.home.today_list.event_model.rows]==['c']
    w.home.set_category('assignment');assert [e.key for e in w.home.today_list.event_model.rows]==['b']
    model=w.home.remaining_table.event_model
    assert model.rowCount()==3 and model.columnCount()==5
    row=next(i for i,e in enumerate(model.rows) if e.key=='a')
    assert [model.data(model.index(row,c)) for c in range(5)]==['과제','기업가정신','기업가정신 글쓰기','10.29 12:00','3일 전']
    assert w.home.today_card.target==2 and w.home.remaining_card.target==3
    assert w.home.category_buttons['assignment'].text()=='과제 1'
    dispose(w,app)

def test_expired_resident_session_shows_login_instead_of_hidden_failure(app,monkeypatch):
    d=CampusLoginDialog(resident=True);d._browser_started=True;d._validation_failed('로그인이 만료됐습니다.')
    assert d.isVisible() and d._recover_after_validation
    d._shutting_down=True;d.dispose();dispose(d,app)
