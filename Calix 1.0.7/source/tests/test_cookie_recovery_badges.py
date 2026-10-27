import time
from types import SimpleNamespace
from datetime import datetime
import pytest
from PySide6.QtCore import Qt,QUrl,QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication,QLabel
from PySide6.QtNetwork import QNetworkCookie
from learning_calendar.login import CampusLoginDialog,COOKIE_PROBE,LOGIN_URL,allow_login_storage,has_cookie_warning
from learning_calendar.calendar_view import DayBadges
from learning_calendar.gui import MainWindow
from learning_calendar.fonts import apply_korean_font
from learning_calendar.design import apply_palette,stylesheet,category_colors

@pytest.fixture(scope='module')
def app():
    app=QApplication.instance() or QApplication([]);app.setStyle('Fusion');apply_korean_font(app);apply_palette(app)
    yield app

@pytest.fixture
def dialog(app):
    d=CampusLoginDialog();d._browser_started=True
    yield d
    d.dispose();d.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()

@pytest.mark.parametrize('text,url',[
    ('쿠키 필요. 계속하기 전에 보안 기본 설정을 조정하십시오.','https://canvas.bufs.ac.kr/login'),
    ('Cookies Required','https://canvas.bufs.ac.kr/'),
    ('','https://canvas.bufs.ac.kr/login?needs_cookies=1')])
def test_canvas_warning_is_detected(text,url):assert has_cookie_warning(text,url)

def test_normal_login_text_is_not_mistaken_for_cookie_warning():
    assert not has_cookie_warning('로그인 / 아이디 / 비밀번호','https://eclass.bufs.ac.kr/xn-sso/login.php')

def test_sso_cookie_policy_allows_school_and_limits_unrelated_third_parties():
    def request(origin,first,third=True):return SimpleNamespace(origin=QUrl(origin),firstPartyUrl=QUrl(first),thirdParty=third)
    assert allow_login_storage(request('https://eclass.bufs.ac.kr','https://canvas.bufs.ac.kr'))
    assert allow_login_storage(request('https://canvas.bufs.ac.kr',''))
    assert not allow_login_storage(request('https://tracking.example','https://canvas.bufs.ac.kr'))

def test_cookie_probe_must_round_trip_before_loading_school(dialog,app):
    deleted=[];urls=[]
    dialog.cookie_store=SimpleNamespace(deleteCookie=lambda cookie,origin:deleted.append(bytes(cookie.name())))
    dialog.view=SimpleNamespace(setUrl=lambda url:urls.append(url.toString()),stop=lambda:None,deleteLater=lambda:None)
    cookie=QNetworkCookie(COOKIE_PROBE,b'1');cookie.setDomain('canvas.bufs.ac.kr');cookie.setPath('/')
    dialog._cookie_added(cookie)
    assert dialog._cookie_storage_ready and deleted==[COOKIE_PROBE] and not dialog.rows and not urls
    dialog._cookie_removed(cookie);app.processEvents()
    assert urls==[LOGIN_URL]

def test_canvas_cookie_warning_recovers_once(dialog,monkeypatch):
    calls=[];dialog.view=SimpleNamespace(url=lambda:QUrl('https://canvas.bufs.ac.kr/login'),stop=lambda:None,deleteLater=lambda:None)
    dialog.page=SimpleNamespace(runJavaScript=lambda script,callback:callback('쿠키 필요. 보안 기본 설정을 조정하십시오.'))
    monkeypatch.setattr(dialog,'_restart_login',lambda:calls.append('restart'))
    dialog._page_loaded(True);dialog._page_loaded(True)
    assert calls==['restart'] and dialog._warning_recovered

def test_cookie_recovery_resets_only_ephemeral_login_store(dialog,monkeypatch,app):
    deleted=[];urls=[]
    dialog.cookie_store=SimpleNamespace(deleteAllCookies=lambda:deleted.append('browser-only'))
    dialog.view=SimpleNamespace(setUrl=lambda url:urls.append(url.toString()),stop=lambda:None,deleteLater=lambda:None)
    dialog.rows[('canvas.bufs.ac.kr','_csrf_token','/')]='old'
    dialog._restart_login();dialog._last_cookie=time.monotonic()-1;dialog._wait_for_cookie_reset()
    assert deleted==['browser-only'] and not dialog.rows and urls==[LOGIN_URL]

def test_two_category_badges_have_separate_semantic_borders(app,tmp_path):
    host=MainWindow(data_dir=tmp_path)
    pair=DayBadges(host);pair.configure(1,5,96,48)
    assert pair.assignment.text()=='과제 1' and pair.movie.text()=='영상 5'
    assert pair.assignment.objectName()=='assignmentBadge' and pair.movie.objectName()=='movieBadge'
    c=category_colors();assert c['assignment_line']!=c['movie_line']
    assert pair.assignment.geometry().right()<pair.movie.geometry().left()
    assert pair.assignment.height()==pair.movie.height()==18
    host.close();host.deleteLater();app.processEvents()

def test_small_cells_use_color_indicators_instead_of_tiny_text(app):
    pair=DayBadges();height=pair.configure(1,5,45,15)
    assert height==8 and pair.assignment.text()=='' and pair.movie.text()==''
    assert '과제 1건' in pair.accessibleName() and '영상 5건' in pair.accessibleName()
    pair.deleteLater();app.processEvents()

def test_app_generated_ui_text_has_no_middle_dot(app,tmp_path):
    w=MainWindow(tmp_path,demo=True);w.show();app.processEvents()
    for label in w.findChildren(QLabel):assert '\u00b7' not in label.text()
    for event in w.home.upcoming.event_model.rows:
        index=w.home.upcoming.event_model.index(w.home.upcoming.event_model.rows.index(event))
        assert '\u00b7' not in index.data()
    w.close();w.deleteLater();app.processEvents()
