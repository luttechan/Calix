from datetime import datetime,timedelta
import pytest
from PySide6.QtCore import Qt,QPoint,QCoreApplication,QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QTableView
from learning_calendar.models import Course,Event,KST
from learning_calendar.gui import MainWindow

@pytest.fixture(scope='module')
def app():return QApplication.instance() or QApplication([])

def test_home_has_data_without_constructing_hidden_calendar(app,tmp_path):
    w=MainWindow(tmp_path);now=datetime.now(KST)
    rows=[Event(f'assignment:1:{n}',1,'과목','assignment',f'일정 {n}',(now+timedelta(days=n+1)).isoformat(),False) for n in range(30)]
    w.store.apply_batch([Course(1,'과목')],{(1,'assignment'):rows});w._reload()
    assert w._calendar is None and w.home.remaining_table.event_model.rowCount()==30
    assert sum(not row.isHidden() for row,_,_ in w.home.remaining_table.rows)==5
    w.set_theme('pink');assert w._calendar is None
    w.select_page(0);calendar=w.calendar;w.select_page(1);w.select_page(0);assert w.calendar is calendar
    w.dispose();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

def test_preview_manual_checkbox_and_whole_list_link(app,tmp_path):
    w=MainWindow(tmp_path);tid=w.store.event_types()[0]['id'];now=datetime.now(KST)
    key=w.store.save_manual_event('긴 이름 '*35,tid,due_at=(now+timedelta(days=1)).isoformat());w._reload();w.show();app.processEvents()
    preview=w.home.remaining_table;row,fields,check=preview.rows[0]
    assert check.isVisible() and fields[2].toolTip()=='긴 이름 '*34+'긴 이름'
    QTest.mouseClick(check,Qt.MouseButton.LeftButton,pos=QPoint(7,check.height()//2));app.processEvents();assert w.snapshot.by_key[key].completed
    w.home.open_remaining();assert w.main_stack.currentIndex()==1 and w.state_select.currentIndex()==1
    w.dispose();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
