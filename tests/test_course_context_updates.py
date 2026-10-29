from types import SimpleNamespace
import time
import pytest
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from learning_calendar.models import Course
from learning_calendar.sync import CampusClient
from learning_calendar.login import CampusLoginDialog,learningx_html_entry,LoginValidation
from tests.test_update_download import server,wait


@pytest.fixture(scope='module')
def app():return QApplication.instance() or QApplication([])


def cleanup(widget,app):
    if hasattr(widget,'dispose'):widget.dispose()
    else:widget.close()
    widget.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()


def test_course_context_used_and_restored_on_failure(monkeypatch):
    client=CampusClient([]);seen=[]
    def pages(path,*args,**kwargs):
        seen.append((path,client.session.headers['Referer']))
        raise ValueError('synthetic')
    monkeypatch.setattr(client,'_paginated',pages)
    with pytest.raises(ValueError):client._course_movies(Course(12,'과목'))
    assert seen==[('/learningx/api/v1/courses/12/modules','https://canvas.bufs.ac.kr/courses/12')]
    assert client.session.headers['Referer']=='https://canvas.bufs.ac.kr/'
    assert client.session.headers['Cache-Control']=='no-cache'
    client.session.close()


@pytest.mark.parametrize('modules',[
    [{'title':'1주차'}],
    [{'module_items':[{'content_data':{'item_content_type':'commons'}}]}],
])
def test_incomplete_course_outline_does_not_replace_video_batch(monkeypatch,modules):
    client=CampusClient([])
    monkeypatch.setattr(client,'_paginated',lambda path,*args,**kwargs:modules if path.endswith('/modules') else [])
    batches,warnings=client._fetch_course(Course(12,'과목'),lambda *_:None)
    assert (12,'movie') not in batches and (12,'assignment') in batches and warnings
    assert not client.course_checks[12]['videos_verified']
    client.session.close()


def test_empty_published_week_is_valid(monkeypatch):
    client=CampusClient([])
    monkeypatch.setattr(client,'_paginated',lambda *args,**kwargs:[{'module_items':[]}])
    assert client._course_movies(Course(12,'과목'))==[]
    client.session.close()


def test_course_html_navigation_fallback_is_scoped_to_the_course():
    doc='<a href="/courses/12/external_tools/49"><span>주차학습</span></a>'
    assert learningx_html_entry(doc,12)=='https://canvas.bufs.ac.kr/courses/12/external_tools/49'
    assert learningx_html_entry(doc,13) is None
    assert learningx_html_entry('<a href="https://evil.example/courses/12/external_tools/49">주차학습</a>',12) is None


@pytest.mark.parametrize('url',[
    'https://canvas.bufs.ac.kr:444/courses/12/external_tools/49',
    'https://user@canvas.bufs.ac.kr/courses/12/external_tools/49',
    'http://canvas.bufs.ac.kr/courses/12/external_tools/49',
])
def test_course_bootstrap_rejects_untrusted_navigation(url):
    assert learningx_html_entry(f'<a href="{url}">주차학습</a>',12) is None


def test_login_uses_course_page_when_tabs_api_is_unavailable(app,monkeypatch):
    import learning_calendar.sync as sync
    class Client:
        _learningx_token=None
        session=SimpleNamespace(close=lambda:None)
        def __init__(self,*args):pass
        def _list_courses(self):return [Course(12,'과목')]
        def _get(self,path):
            if path.endswith('/profile'):return SimpleNamespace(json=lambda:{'id':1})
            raise ValueError('tabs unavailable')
        def _course_document(self,cid):return '<a href="/courses/12/external_tools/49">주차학습</a>'
    monkeypatch.setattr(sync,'CampusClient',Client)
    task=LoginValidation([]);results=[];task.checked.connect(results.append);task.run()
    assert results[0]['canvas_valid'] and results[0]['courses']==[{'id':12,'name':'과목'}]
    assert not results[0]['videos_verified']


def test_expired_bootstrap_does_not_report_a_completed_login(app):
    dialog=CampusLoginDialog();dialog._browser_started=True
    dialog._validated=True;dialog._pending_accept=True;dialog._bootstrap_active=True
    dialog._bootstrap_deadline=time.monotonic()-1;completed=[]
    dialog.session_ready.connect(completed.append);dialog._bootstrap_tick()
    assert not completed and not dialog._validated and not dialog._finish_after_validation
    assert not dialog.authenticated and '다시' in dialog.message.text()
    cleanup(dialog,app)


def test_token_validation_is_throttled_without_blocking_link_discovery(app,monkeypatch):
    dialog=CampusLoginDialog();dialog._browser_started=True
    dialog._validated=True;dialog._pending_accept=True;dialog._bootstrap_deadline=time.monotonic()+30
    dialog._link_check_at=0;checks=[];links=[]
    monkeypatch.setattr(dialog,'_has_token',lambda:True)
    monkeypatch.setattr(dialog,'accept_after_cookie_capture',lambda:checks.append(True))
    monkeypatch.setattr(dialog,'_find_learningx_link',lambda:links.append(True))
    dialog._bootstrap_tick();dialog._bootstrap_tick()
    assert len(checks)==1 and len(links)==1
    cleanup(dialog,app)


def test_new_release_notice_does_not_open_a_dialog_or_download(app,tmp_path):
    from learning_calendar.gui import MainWindow
    from learning_calendar.updates import Release
    window=MainWindow(tmp_path)
    assert not window.update_timer.isActive()
    window._update_checked(Release('v99.0.0',''))
    assert window.update_button.text()=='업데이트 가능' and not window._dialogs and window._update_probe is None
    cleanup(window,app)


def test_closing_window_cancels_scheduled_update_check(app,tmp_path):
    from learning_calendar.gui import MainWindow
    window=MainWindow(tmp_path);window.update_timer.start(8000)
    calls=[];window._update_probe=SimpleNamespace(close=lambda:calls.append('closed'))
    window.dispose()
    assert not window.update_timer.isActive() and window._update_probe is None and calls==['closed']
    cleanup(window,app)


def test_automatic_check_uses_real_qt_network_without_a_visible_dialog(app,tmp_path,server,monkeypatch):
    import learning_calendar.update_dialog as module
    from learning_calendar.gui import MainWindow
    base,_=server;monkeypatch.setattr(module,'LATEST_API',base+'/api')
    window=MainWindow(tmp_path);window._check_updates_in_background()
    assert window._update_probe is not None and not window._update_probe.isVisible()
    wait(app,lambda:window._update_probe is None)
    assert window.update_button.text()=='업데이트 가능' and not window._dialogs
    cleanup(window,app)
