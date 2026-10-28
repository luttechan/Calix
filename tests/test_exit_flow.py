from types import SimpleNamespace
import pytest
from PySide6.QtCore import QCoreApplication,QEvent,QTimer,Qt
from PySide6.QtWidgets import QApplication,QMessageBox
from learning_calendar.gui import MainWindow
from learning_calendar.diary_store import DiaryStore

@pytest.fixture
def window(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(app,'quit',lambda:None)
    w=MainWindow(tmp_path);w.show();app.processEvents()
    yield w
    if not w._closed:w.dispose()
    w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()

def dirty_diary(window):
    window.show_diary();page=window.diary;page.new_entry();key=page.current_id
    page.body.setPlainText('저장된 본문');assert page.flush()
    page.body.setPlainText('저장 전 본문');assert page.dirty and page.save_timer.isActive()
    return page,key

def read_diary(folder,key):
    store=DiaryStore(folder/'journals.db')
    try:return store.read(key)
    finally:store.close()

def test_x_does_not_close_and_sidebar_exit_is_available(window):
    assert not window.windowFlags() & Qt.WindowType.WindowCloseButtonHint
    assert window.exit_button.isVisible() and window.exit_button.text()=='종료'
    window.close();QApplication.processEvents()
    assert window.isVisible() and not window._closed and not window._closing

@pytest.mark.parametrize('pending',[False,True])
def test_exit_dialog_exact_copy_buttons_and_default_cancel(window,pending):
    observed={}
    def inspect():
        box=QApplication.activeModalWidget();observed['text']=box.text()
        observed['buttons']=[button.text() for button in box.buttons()]
        observed['default']=box.defaultButton().text()
        next(button for button in box.buttons() if button.text()=='취소').click()
    QTimer.singleShot(0,inspect)
    assert window._confirm_exit(pending)=='cancel'
    assert observed['text']==('변경 사항이 있습니다. 종료하시겠습니까?' if pending else '종료하시겠습니까?')
    assert set(observed['buttons'])==({'저장하고 종료','바로 종료','취소'} if pending else {'종료','취소'})
    assert observed['default']=='취소'

def test_cancel_exit_keeps_pending_diary_and_restarts_autosave(window,monkeypatch):
    page,key=dirty_diary(window);states=[]
    def cancel(pending):
        states.append((pending,page.save_timer.isActive()));return 'cancel'
    monkeypatch.setattr(window,'_confirm_exit',cancel);window.request_exit()
    assert states==[(True,False)]
    assert window.isVisible() and page.dirty and page.save_timer.isActive()
    assert page.body.toPlainText()=='저장 전 본문'

@pytest.mark.parametrize('choice,expected',[('save','저장 전 본문'),('discard','저장된 본문')])
def test_exit_choice_saves_or_discards_only_pending_content(window,monkeypatch,tmp_path,choice,expected):
    page,key=dirty_diary(window)
    monkeypatch.setattr(window,'_confirm_exit',lambda pending:choice)
    window.request_exit();QApplication.processEvents()
    assert window._closed and not window.isVisible()
    assert read_diary(tmp_path,key)['body']==expected

def test_failed_save_prevents_exit(window,monkeypatch):
    page,key=dirty_diary(window)
    monkeypatch.setattr(window,'_confirm_exit',lambda pending:'save')
    monkeypatch.setattr(page,'flush',lambda:False)
    window.request_exit()
    assert window.isVisible() and not window._closing and not window._exit_confirmed
    assert page.dirty and page.save_timer.isActive()
    monkeypatch.undo()

def test_shutdown_cancels_sync_and_browser_together_and_finishes(window,monkeypatch):
    events=[];state={'running':True}
    def cancel():
        events.append('sync cancel');QTimer.singleShot(60,lambda:state.update(running=False))
    window._thread=SimpleNamespace(isRunning=lambda:state['running'],cancel=cancel,deleteLater=lambda:None)
    window._login_process=SimpleNamespace(kill=lambda:events.append('browser kill'))
    def command(value):
        events.append(value);QTimer.singleShot(80,lambda:setattr(window,'_login_process',None));return True
    monkeypatch.setattr(window,'_browser_command',command)
    monkeypatch.setattr(window,'_confirm_exit',lambda pending:'discard')
    window.request_exit()
    assert events==['sync cancel','quit'] and window.isVisible() and not window._closed
    from PySide6.QtTest import QTest
    QTest.qWait(180);QApplication.processEvents()
    assert window._closed and not window._shutdown_poll.isActive()

def test_unresponsive_owned_browser_is_killed_and_application_quits(window,monkeypatch):
    events=[]
    def kill():
        events.append('killed');window._login_process=None
    window._login_process=SimpleNamespace(kill=kill)
    monkeypatch.setattr(window,'_browser_command',lambda command:events.append(command))
    monkeypatch.setattr(window,'_confirm_exit',lambda pending:'save')
    monkeypatch.setattr(QApplication.instance(),'quit',lambda:events.append('app quit'))
    window.request_exit()
    assert events==['quit'] and not window._closed
    assert not window.isEnabled()
    from PySide6.QtTest import QTest
    QTest.qWait(1700);QApplication.processEvents()
    assert events==['quit','killed','app quit'] and window._closed
