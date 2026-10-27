from datetime import datetime,timedelta
import time
from PySide6.QtCore import Qt,QCoreApplication,QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from learning_calendar.gui import MainWindow
from learning_calendar.models import Event,Course,KST
from learning_calendar.snapshot import Snapshot

def close(window,app):
    window.dispose();window.deleteLater()
    QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()

def test_assignment_click_skips_hidden_home_and_snapshot_reconstruction(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([]);w=MainWindow(tmp_path);now=datetime.now(KST)
    rows=[Event(f'assignment:1:{i}',1,'과목','assignment',f'과제 {i}',(now+timedelta(days=i%20+1)).isoformat(),False) for i in range(5000)]
    w.snapshot=Snapshot(rows,[Course(1,'과목')]);w._reload_course_filter();w.refresh();w.show();app.processEvents()
    calls=[];original=w.home.update_snapshot
    monkeypatch.setattr(w.home,'update_snapshot',lambda *args,**kwargs:calls.append('home'))
    def forbidden(*args,**kwargs):raise AssertionError('navigation must not rebuild the source snapshot')
    monkeypatch.setattr(Snapshot,'__init__',forbidden)
    start=time.perf_counter();QTest.mouseClick(w.nav[2],Qt.MouseButton.LeftButton);app.processEvents()
    assert time.perf_counter()-start<2
    assert w.tabs.currentIndex()==2 and w.assignment_list.model().rowCount()==5000
    assert not calls and w.main_stack._overlay is None
    monkeypatch.setattr(w.home,'update_snapshot',original)
    w.show_home(animate=False);assert w.home.remaining_table.event_model.rowCount()==5000
    close(w,app)

def test_rapid_menu_clicks_keep_last_page_responsive_and_release_animation(tmp_path):
    app=QApplication.instance() or QApplication([]);w=MainWindow(tmp_path);w.show();app.processEvents()
    for page in (2,1,0,2,3,2)*5:
        QTest.mouseClick(w.nav[page],Qt.MouseButton.LeftButton)
        assert w.tabs.currentIndex()==page and w.main_stack.currentIndex()==1
        assert w.heading.text()==('달력','동영상','과제','시간표')[page]
    QTest.qWait(180);app.processEvents()
    assert w.main_stack._group is None and w.main_stack._overlay is None
    assert w.detail_workspace.pos()==w.main_stack.contentsRect().topLeft()
    w.show_home();QTest.mouseClick(w.nav[2],Qt.MouseButton.LeftButton)
    w.resize(1100,740);app.processEvents()
    assert w.assignment_list.isVisible() and w.main_stack._group is None
    close(w,app)
