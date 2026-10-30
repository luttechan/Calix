from datetime import date
import pytest
from PySide6.QtCore import Qt,QRect,QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from learning_calendar.event_popover import EventPopover
from learning_calendar.models import Event
from learning_calendar.design import colors

@pytest.fixture
def app():return QApplication.instance() or QApplication([])

def events():return [Event(str(i),i,'강의 '+str(i),'movie','영상 '+str(i),'2026-11-08T23:59:00+09:00',False) for i in (1,2)]

def pump(app):app.processEvents();QTest.qWait(10)

def assert_surface(popup):
    image=popup.grab().toImage();expected=colors()['surface'].lower()
    for x,y in ((4,popup.height()//2),(popup.width()//2,8),(popup.width()-5,popup.height()//2)):
        pixel=image.pixelColor(x,y);assert pixel.alpha()==255 and pixel.name().lower()==expected
    assert image.pixelColor(0,0).alpha()==0
    assert popup.windowTitle()=='상세 일정'

@pytest.mark.parametrize('theme',['pink','sky','mint','purple','dark'])
def test_surface_stays_opaque_while_selecting_and_filtering(app,theme):
    app.setProperty('bufsTheme',theme);popup=EventPopover(date(2026,11,8),events(),[],lambda *args:True);popup.show();pump(app)
    assert_surface(popup)
    popup.list.setCurrentIndex(popup.list.model().index(1,0));pump(app);assert_surface(popup)
    popup.query.setText('no matching result');popup.filter_choices();pump(app);assert_surface(popup)
    popup.query.clear();popup.filter_choices();pump(app);assert_surface(popup)
    popup.close();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

@pytest.mark.parametrize('theme',['sky','dark'])
def test_dirty_region_resize_and_move_do_not_clear_background(app,theme):
    app.setProperty('bufsTheme',theme);popup=EventPopover(date(2026,11,8),events(),[],lambda *args:True);popup.show();pump(app)
    popup.update(QRect(0,0,32,popup.height()));pump(app);assert_surface(popup)
    popup.resize(530,760);popup.move(popup.pos().x()+12,popup.pos().y()+12);pump(app);assert_surface(popup)
    popup.close();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

def test_reopening_detail_never_reuses_a_transparent_surface(app):
    app.setProperty('bufsTheme','purple')
    for _ in range(10):
        popup=EventPopover(date(2026,11,8),events(),[],lambda *args:True);popup.show();pump(app);assert_surface(popup)
        popup.close();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

@pytest.mark.parametrize('theme',['purple','dark'])
def test_calendar_background_behind_detail_is_preserved(app,tmp_path,theme):
    from learning_calendar.gui import MainWindow
    from learning_calendar.models import Course
    from PySide6.QtCore import QPoint
    window=MainWindow(tmp_path);window.set_theme(theme);rows=events()
    window.store.apply_batch([Course(1,'강의 1'),Course(2,'강의 2')],{(i,'movie'):[row for row in rows if row.course_id==i] for i in (1,2)})
    window._reload();window.select_page(0);window.select_day(date(2026,11,8));window.main_stack._settle();window.show();pump(app);window.calendar._layout_badges()
    view=window.calendar.view
    def sample_calendar():
        image=view.viewport().grab().toImage();samples=[]
        for i in range(42):
            rect=view.visualRect(view.model().index(i//7+1,i%7));samples.append(image.pixelColor(rect.left()+6,rect.center().y()).getRgb())
        return samples
    before=sample_calendar();background_key=window.centralWidget()._field.cacheKey()
    popup=window.show_calendar_details(date(2026,11,8),rows,window.mapToGlobal(QPoint(300,300)));pump(app);assert_surface(popup)
    popup.list.setCurrentIndex(popup.list.model().index(1,0));pump(app)
    assert sample_calendar()==before and window.centralWidget()._field.cacheKey()==background_key
    popup.close();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);pump(app);assert sample_calendar()==before
    window.dispose();window.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
