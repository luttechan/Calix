from dataclasses import replace
from datetime import datetime,timedelta
import pytest
from PySide6.QtCore import Qt,QPoint,QEvent,QCoreApplication,QRect
from PySide6.QtWidgets import QApplication,QWidget,QVBoxLayout,QMainWindow,QLabel
from PySide6.QtTest import QTest,QSignalSpy
from learning_calendar.models import Event,Course,KST
from learning_calendar.gui import MainWindow

@pytest.fixture(scope='module')
def app():return QApplication.instance() or QApplication([])

@pytest.fixture
def window(app,tmp_path):
    w=MainWindow(tmp_path);now=datetime.now(KST).replace(hour=23,minute=59,second=59)
    rows=[Event('assignment:1:1',1,'강의 A','assignment','보고서',now.isoformat(),False),Event('movie:1:2',1,'강의 A','movie','학습 영상',now.isoformat(),False),Event('assignment:2:3',2,'강의 B','assignment','다른 과제',now.isoformat(),False)]
    w.store.apply_batch([Course(1,'강의 A'),Course(2,'강의 B')],{(1,'assignment'):[rows[0]],(1,'movie'):[rows[1]],(2,'assignment'):[rows[2]]});w._reload();w.show();app.processEvents()
    yield w
    w.dispose();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()

def open_choices(w):
    w.show_calendar_details(w.selected_date,w.snapshot.events,QPoint(200,100));return w._event_popover

def test_multiple_events_select_course_type_and_title_without_dismiss(window,app):
    popup=open_choices(window);assert popup.list.model().columnCount()==3 and popup.chooser.isVisible()
    assert [popup.list.model().headerData(i,Qt.Orientation.Horizontal) for i in range(3)]==['강의','Type','할 일 이름']
    popup.course_filter.setCurrentIndex(popup.course_filter.findData(1));assert popup.list.model().rowCount()==2
    popup.kind_filter.setCurrentIndex(popup.kind_filter.findData('movie'));assert popup.list.model().rowCount()==1 and popup.current.key=='movie:1:2'
    popup.query.setText('없는 이름');QTest.qWait(180);assert popup.empty.isVisible() and popup.list.model().rowCount()==0
    assert not popup.editor.isVisible() and not popup.save_button.isEnabled()
    popup.query.clear();QTest.qWait(180);assert popup.list.model().rowCount()==1
    for combo in (popup.course_filter,popup.kind_filter,popup.type):
        combo.showPopup();app.processEvents();combo.hidePopup();app.processEvents();assert popup.isVisible() and window.isVisible()
    app.sendEvent(popup,QEvent(QEvent.Type.WindowDeactivate));app.processEvents();assert popup.isVisible()
    assert popup.windowType()==Qt.WindowType.Tool and not popup.testAttribute(Qt.WidgetAttribute.WA_QuitOnClose)

def test_selecting_another_event_saves_without_model_reset(window,app):
    popup=open_choices(window);model=popup.list.model();reset=QSignalSpy(model.modelReset)
    first=popup.current.key;popup.note.setPlainText('첫 항목 메모')
    rect=popup.list.visualRect(model.index(1,2));QTest.mouseClick(popup.list.viewport(),Qt.MouseButton.LeftButton,pos=rect.center());app.processEvents()
    assert popup.current.key!=first and window.snapshot.by_key[first].note=='첫 항목 메모'
    assert reset.count()==0 and popup.isVisible() and window.isVisible()
    for i in range(30):
        key=popup.current.key;popup.note.setPlainText(f'메모 {i}');popup.list.setCurrentIndex(model.index((i+2)%3,2));app.processEvents()
        assert window.snapshot.by_key[key].note==f'메모 {i}' or popup.current.key==key
    assert reset.count()==0 and popup.isVisible()

def test_category_changes_keep_opaque_background_and_frame_cache(window,app):
    for theme in ('sky','dark'):
        window.set_theme(theme);window.show_home(animate=False);app.processEvents();root=window.centralWidget();count=root.render_count
        patch=QRect(190,0,300,10);original=root.grab().toImage().copy(patch)
        for category in ('assignment','movie','all')*3:
            window.home.set_category(category);app.processEvents();assert root.grab().toImage().copy(patch)==original
        window.select_page(0)
        animation=window.main_stack._group;assert animation is not None
        assert window.main_stack._overlay is None
        for progress in (0.,.25,.5,.75):
            animation.setCurrentTime(round(animation.duration()*progress))
            frame=root.grab().toImage().copy(patch)
            assert frame==original
        window.main_stack._settle();app.processEvents();assert root.render_count==count

def test_escape_closes_only_details_and_preserves_edits(window,app):
    popup=open_choices(window);key=popup.current.key;popup.note.setPlainText('닫으며 저장')
    QTest.keyClick(popup,Qt.Key.Key_Escape);QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
    assert window.isVisible() and window._event_popover is None and window.snapshot.by_key[key].note=='닫으며 저장'

def test_calendar_chip_starts_with_its_type_but_can_show_other_types(window):
    window.select_page(0);window.main_stack._settle();movies=[e for e in window.snapshot.events if e.kind=='movie']
    window.show_calendar_group(window.selected_date,movies,QPoint(200,100));popup=window._event_popover
    assert len(popup.rows)==3 and popup.kind_filter.currentData()=='movie' and popup.list.model().rowCount()==1
    popup.kind_filter.setCurrentIndex(0);assert popup.list.model().rowCount()==3
