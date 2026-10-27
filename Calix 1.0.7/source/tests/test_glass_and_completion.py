from datetime import datetime
import pytest
from PySide6.QtCore import QCoreApplication,QEvent,Qt,QPoint
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from learning_calendar.gui import MainWindow
from learning_calendar.preferences import read_settings
from learning_calendar.design import glass_enabled,stylesheet
from learning_calendar.models import KST

@pytest.fixture(scope='module')
def app():return QApplication.instance() or QApplication([])

@pytest.fixture
def window(app,tmp_path):
    w=MainWindow(tmp_path);w.show();app.processEvents()
    yield w
    w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()

def test_glass_toggle_persists_without_replacing_native_font(window,app):
    font=app.font();assert glass_enabled()
    window.set_glass(False);app.processEvents();assert not glass_enabled() and read_settings(window.settings_path)['glass'] is False
    assert window.centralWidget()._field is None and app.font()==font
    window.set_glass(True);app.processEvents();assert glass_enabled() and read_settings(window.settings_path)['glass'] is True and app.font()==font

def test_glass_background_cache_is_small_and_reused_on_repaint_and_resize(window,app):
    root=window.centralWidget();app.processEvents();initial=root.render_count
    assert root._field.width()==640 and root._field.height()==420 and root._field.sizeInBytes()<=1200000
    for _ in range(4):root.repaint();app.processEvents()
    window.resize(1500,900);app.processEvents();root.repaint()
    assert root.render_count==initial
    window.set_theme('mint');app.processEvents();assert root.render_count==initial+1

def test_calendar_text_keeps_opaque_surface_with_glass(window):
    sheet=stylesheet(window.theme_key)
    assert 'QCalendarWidget QTableView {background:#FFFFFF;border:0;}' in sheet

def test_manual_completion_checkbox_works_in_table_and_calendar(window,app):
    w=window;tid=w.store.event_types()[0]['id'];stamp=datetime.now(KST).replace(hour=23,minute=59,second=59).isoformat();key=w.store.save_manual_event('체크 표시 검사',tid,due_at=stamp);w._reload();app.processEvents()
    table=w.home.remaining_table;check=table.rows[0][2];assert check.isVisible()
    QTest.mouseClick(check,Qt.MouseButton.LeftButton,pos=QPoint(7,check.height()//2));app.processEvents()
    assert next(e for e in w.store.events() if e.key==key).completed
    w.undo_manual();w.select_page(0);w.day_toggle.setChecked(True);w.main_stack._settle();app.processEvents();view=w.day_list;rect=view.visualRect(view.model().index(0));assert rect.isValid()
    QTest.mouseClick(view.viewport(),Qt.MouseButton.LeftButton,pos=QPoint(rect.left()+24,rect.top()+28));app.processEvents()
    assert next(e for e in w.store.events() if e.key==key).completed
