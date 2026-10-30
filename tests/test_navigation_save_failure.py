from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication,QEvent
from learning_calendar.gui import MainWindow


def test_failed_diary_save_keeps_current_page_and_text(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([]);window=MainWindow(tmp_path)
    window.show_diary();page=window.diary;page.new_entry();page.body.setPlainText('저장 대기 중인 내용')
    monkeypatch.setattr(page,'flush',lambda:False)
    selected=window.main_stack.currentIndex()
    window.select_page(2)
    assert window.main_stack.currentIndex()==selected and page.body.toPlainText()=='저장 대기 중인 내용'
    window.show_home()
    assert window.main_stack.currentIndex()==selected and page.dirty
    page.discard_pending();window.dispose();window.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
