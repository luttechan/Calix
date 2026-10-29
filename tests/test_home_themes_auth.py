"""Regression tests for the home flow and the reported cookie failure."""
from datetime import datetime,timedelta
import pytest
from PySide6.QtCore import QCoreApplication,QEvent,Qt
from PySide6.QtWidgets import QApplication,QWidget
from learning_calendar.cookies import canvas_session_available,applies_to_canvas
from learning_calendar.sync import CampusClient,LearningXTokenMissing
from learning_calendar.models import Event,Course,KST
from learning_calendar.snapshot import Snapshot
from learning_calendar.gui import MainWindow
from learning_calendar.design import apply_palette,THEME_NAMES
from learning_calendar.fonts import apply_korean_font

@pytest.fixture(scope='module')
def app():
    app=QApplication.instance() or QApplication([]);app.setStyle('Fusion');apply_korean_font(app);apply_palette(app)
    yield app

@pytest.fixture
def window(app,tmp_path):
    w=MainWindow(tmp_path);w.show();app.processEvents()
    yield w
    w.dispose();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()

def test_home_counts_exclude_expired_and_completed(window):
    now=datetime.now(KST)
    events=[Event(str(i),1,'과목','assignment','일정',due,done) for i,(due,done) in enumerate([
        ((now-timedelta(days=2)).isoformat(),False),(now.replace(hour=23,minute=59,second=59).isoformat(),False),
        ((now+timedelta(days=2)).isoformat(),False),(None,False),(now.isoformat(),True)])]
    window.snapshot=Snapshot(events,[Course(1,'과목')]);window.refresh()
    assert window.main_stack.currentIndex()==0
    assert window.home.today_card.target==1
    assert window.home.remaining_card.target==3
    window.open_details('today');window.main_stack._settle()
    assert len(window._filtered)==1 and window.main_stack.currentIndex()==1
    window.show_home();window.main_stack._settle()
    assert window.home.hero.isVisible()

def test_all_five_themes_persist_and_keep_font(window,app):
    from learning_calendar.preferences import read_settings
    font=app.font()
    for key in THEME_NAMES:
        window.set_theme(key);app.processEvents()
        assert app.property('bufsTheme')==key
        assert read_settings(window.settings_path)['theme']==key
        assert app.font()==font

def test_hidden_home_stops_ambient_animation(window,app):
    window.resize(1240,840)
    window.show_home();window.main_stack._settle();app.processEvents()
    assert window.home.hero.clock.isActive()
    window.select_page(0);window.main_stack._settle();app.processEvents()
    assert not window.home.hero.clock.isActive()

def test_repeated_home_transitions_release_overlays(window,app):
    from PySide6.QtTest import QTest
    for _ in range(4):
        window.show_home();window.select_page(0);window.main_stack._settle()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
    before=len(window.findChildren(QWidget))
    for _ in range(40):
        window.show_home();window.select_page(0);window.main_stack._settle()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
    assert len(window.findChildren(QWidget))<=before

def test_canvas_cookie_is_sufficient_without_movie_token():
    rows=[{'name':'_normandy_session','domain':'.canvas.bufs.ac.kr','path':'/','value':'test-session','secure':True}]
    assert canvas_session_available(rows)
    assert not any(r['name']=='xn_api_token' for r in rows)
    assert not canvas_session_available([{'name':'_csrf_token','domain':'canvas.bufs.ac.kr','value':'x'}])

def test_parent_domain_cookie_is_preserved_but_unrelated_domains_are_not():
    rows=[{'name':'_normandy_session','domain':'.bufs.ac.kr','value':'parent-session','path':'/','secure':True},
          {'name':'sso','domain':'eclass.bufs.ac.kr','value':'not-for-canvas','path':'/'}]
    client=CampusClient(rows)
    try:
        assert '_normandy_session' in client.session.cookies.keys()
        assert 'sso' not in client.session.cookies.keys()
        assert applies_to_canvas('.bufs.ac.kr')
        assert not applies_to_canvas('fakecanvas.bufs.ac.kr')
    finally:client.session.close()

def test_duplicate_domain_cookies_do_not_send_duplicate_session_headers():
    rows=[{'name':'_normandy_session','domain':'.bufs.ac.kr','value':'parent','path':'/'},
          {'name':'_normandy_session','domain':'.canvas.bufs.ac.kr','value':'host','path':'/'},
          {'name':'_normandy_session','domain':'canvas.bufs.ac.kr','value':'latest','path':'/'}]
    client=CampusClient(rows)
    try:
        assert len(client.session.cookies)==1
        assert client.session.cookies.get('_normandy_session')=='latest'
    finally:client.session.close()

def test_missing_learningx_token_still_fetches_assignments(monkeypatch):
    client=CampusClient([])
    class Response:
        def json(self):return [{'id':1,'longName':'과목'}]
    def fake_get(path,params=None):
        if path.endswith('/modules'):raise LearningXTokenMissing('token missing')
        return Response()
    def paginate(path,params=None,**kwargs):
        if path.endswith('/courses'):return [{'id':1,'name':'과목'}]
        if path.endswith('/modules'):raise LearningXTokenMissing('token missing')
        if path.endswith('/assignments'):return [{'id':2,'name':'보고서'}]
        return []
    monkeypatch.setattr(client,'_get',fake_get);monkeypatch.setattr(client,'_paginated',paginate)
    courses,batches,warnings=client.fetch()
    assert batches[(1,'assignment')][0].title=='보고서'
    assert (1,'movie') not in batches and warnings
    client.session.close()

def test_manual_sync_reuses_canvas_session_instead_of_opening_login(window,monkeypatch):
    import learning_calendar.cookies as cookies
    import learning_calendar.worker as worker
    from PySide6.QtCore import QObject,Signal
    class Task(QObject):
        progress=Signal(str);success=Signal(object);error=Signal(str);authentication_required=Signal(str);finished=Signal()
        def __init__(self,*args,**kwargs):super().__init__();self.started=False
        def start(self):self.started=True
    rows=[{'name':'_normandy_session','domain':'canvas.bufs.ac.kr','path':'/','value':'test-session'}]
    monkeypatch.setattr(cookies,'read_cookies',lambda path:rows)
    monkeypatch.setattr(worker,'SyncTask',Task)
    monkeypatch.setattr(window,'_start_login',lambda *args:pytest.fail('session cookie must be reused'))
    window.manual_sync(dom_snapshot={'owner':'1','results':[]})
    assert window._thread.started
    window._thread=None;window._set_busy(False)

def test_login_shell_is_topmost_and_visible_before_browser_import(app,tmp_path,monkeypatch):
    from learning_calendar.login import CampusLoginDialog
    from PySide6.QtTest import QTest
    ready=tmp_path/'login.ready';dialog=CampusLoginDialog(ready_file=ready)
    calls=[];monkeypatch.setattr(dialog,'_initialize_browser',lambda:calls.append('browser'))
    dialog.show();app.processEvents()
    assert dialog.isVisible() and ready.exists()
    assert dialog.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert not calls
    from time import monotonic
    deadline=monotonic()+1
    while not calls and monotonic()<deadline:QTest.qWait(10)
    assert calls==['browser']
    dialog.reject();dialog.dispose();dialog.deleteLater();app.processEvents()

def test_verified_login_accepts_canvas_cookies_without_learningx_token(app):
    from learning_calendar.login import CampusLoginDialog
    dialog=CampusLoginDialog();dialog._browser_started=True
    row={'name':'_normandy_session','domain':'canvas.bufs.ac.kr','path':'/','value':'test','raw':'synthetic'}
    dialog.rows[dialog._key(row)]=row;dialog._validated=True;dialog._pending_accept=True
    dialog._complete()
    assert dialog.result()==1 and dialog.session_rows==[row]
    dialog.dispose();dialog.deleteLater();app.processEvents()

def test_dpapi_cookie_round_trip_including_university_parent_domain(app,tmp_path):
    from PySide6.QtNetwork import QNetworkCookie
    from learning_calendar.cookies import cookie_record,write_cookies,read_cookies
    cookie=QNetworkCookie(b'_normandy_session',b'synthetic-test-session')
    cookie.setDomain('.bufs.ac.kr');cookie.setPath('/');cookie.setSecure(True)
    rec=cookie_record(cookie);assert rec
    path=tmp_path/'test.dpapi';write_cookies(path,[rec]);rows=read_cookies(path)
    assert len(rows)==1 and rows[0]['value']=='synthetic-test-session'
    assert b'synthetic-test-session' not in path.read_bytes()

def test_expired_session_requests_login_after_worker_finishes(window,monkeypatch):
    calls=[];monkeypatch.setattr(window,'_start_login',lambda then_sync:calls.append(then_sync))
    window._sync_auth_required('401')
    assert not calls
    window._sync_finished()
    assert calls==[True] and window._reauth_attempted

def test_home_text_and_controls_are_native_widgets(window):
    from PySide6.QtWidgets import QLabel,QPushButton,QCalendarWidget
    assert isinstance(window.home.hero.greeting,QLabel)
    assert isinstance(window.home.today_card,QPushButton)
    assert isinstance(window.home.today_card.number_label,QLabel)
    assert all(isinstance(b,QPushButton) for b in window.nav)
    assert isinstance(window.calendar,QCalendarWidget)

def test_animation_advances_and_pauses_when_home_is_hidden(window,app):
    from PySide6.QtTest import QTest
    window.resize(1240,840);window.show_home();window.main_stack._settle();QTest.qWait(900)
    before=window.home.hero.orbit.phase
    frame=window.home.hero.orbit.grab().toImage()
    QTest.qWait(160)
    assert window.home.hero.orbit.phase>before
    assert window.home.hero.orbit.grab().toImage()!=frame
    window.select_page(0);window.main_stack._settle();app.processEvents()
    paused=window.home.hero.orbit.phase;QTest.qWait(100)
    assert window.home.hero.orbit.phase==paused

def test_text_uses_actual_pretendard_without_artificial_tracking(window,app):
    from PySide6.QtGui import QFontInfo,QFont
    window.resize(1240,840);app.processEvents()
    for widget in [window.home.hero.greeting,window.home.today_card.number_label,window.home.today_card.title_label,*window.nav]:
        assert QFontInfo(widget.font()).family()==app.property('bufsFontFamily')
        font=widget.font()
        assert font.letterSpacing() in (0,100) if font.letterSpacingType()==QFont.SpacingType.PercentageSpacing else font.letterSpacing()==0
    assert window.nav[0].font().pixelSize()==14
