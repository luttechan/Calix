from datetime import date,datetime,timedelta
import pytest
from PySide6.QtCore import Qt,QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from learning_calendar.calendar_view import MonthCanvas
from learning_calendar.models import Course,Event,KST
from learning_calendar.snapshot import Snapshot
from learning_calendar.gui import MainWindow

@pytest.fixture(scope='module')
def app():return QApplication.instance() or QApplication([])

def settle(app):
    for _ in range(4):app.processEvents()

def dispose(widget,app):
    widget.close();widget.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()

@pytest.mark.parametrize('year,month',[(2026,2),(2026,3),(2026,6),(2026,10),(2026,11),(2027,1)])
def test_badges_follow_native_date_cells_for_every_day(app,year,month):
    from calendar import monthrange
    rows={}
    for day in range(1,monthrange(year,month)[1]+1):
        stamp=datetime(year,month,day,23,59,tzinfo=KST).isoformat()
        rows[date(year,month,day)]=[Event(f'v{day}',1,'과목','movie','날짜 검사',stamp,False)]
    widget=MonthCanvas();widget.resize(1000,650);widget.set_month(date(year,month,1),date(year,month,1),rows);widget.show();settle(app)
    visible=[badge for badge in widget.badges if badge.isVisible()]
    assert len(visible)==len(rows)
    for badge in visible:
        day=date.fromisoformat(badge.property('calendarDate'));index=widget.view.indexAt(badge.geometry().center())
        assert index.isValid() and widget.view.model().data(index,Qt.ItemDataRole.DisplayRole)==day.day
        assert badge.movie.isVisible() and badge.movie.text()=='영상 1'
    dispose(widget,app)

def test_november_29_video_list_and_overlay_agree_after_navigation_and_resize(app,tmp_path):
    w=MainWindow(tmp_path);stamp='2026-11-29T14:59:59Z'
    movies=[Event('v1',1,'과목','movie','영상 1',stamp,False),Event('v2',1,'과목','movie','영상 2',stamp,False)]
    w.snapshot=Snapshot(movies,[Course(1,'과목')]);w._reload_course_filter();w.show();w.select_page(1);w.main_stack._settle();settle(app)
    assert w.video_list.event_model.rowCount()==2
    w.select_page(0);w.select_day(date(2026,11,29));w.main_stack._settle();settle(app)
    for width,height in ((1240,840),(980,700),(1540,920)):
        w.resize(width,height);settle(app)
        badge=next(b for b in w.calendar.badges if b.property('calendarDate')=='2026-11-29')
        index=w.calendar.view.indexAt(badge.geometry().center())
        assert w.calendar.view.model().data(index)==29 and badge.isVisible() and badge.movie.isVisible()
        assert '영상 2건' in badge.accessibleName() and len(w.day_list.event_model.rows)==2
        wrong=next(b for b in w.calendar.badges if b.property('calendarDate')=='2026-11-22')
        assert not wrong.isVisible()
    w.shift_month(1);settle(app);w.shift_month(-1);settle(app)
    badge=next(b for b in w.calendar.badges if b.property('calendarDate')=='2026-11-29');assert badge.isVisible() and '영상 2건' in badge.accessibleName()
    dispose(w,app)
