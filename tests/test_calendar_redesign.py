from datetime import date
import pytest
from PySide6.QtCore import Qt,QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from learning_calendar.gui import MainWindow
from learning_calendar.calendar_view import DayBadges

@pytest.fixture(scope='module')
def app():return QApplication.instance() or QApplication([])

def test_full_width_calendar_and_contextual_detail_panel(app,tmp_path):
    w=MainWindow(tmp_path);w.resize(1360,860);w.show();w.select_page(0);w.main_stack._settle();app.processEvents()
    wide=w.calendar.width();assert not w.day_panel.isVisible() and not w.metrics.isVisible()
    assert w.calendar.view.visualRect(w.calendar.view.model().index(0,0)).height()==34
    w.day_toggle.click();app.processEvents();assert w.day_panel.isVisible() and w.calendar.width()<wide
    w.day_toggle.click();app.processEvents();assert not w.day_panel.isVisible() and w.calendar.width()==wide
    w.dispose();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()

def test_many_custom_types_stay_on_one_line_with_complete_accessible_counts(app):
    badge=DayBadges();height=badge.configure(1,2,160,95,[('운동',3,'#3AA68E'),('할 일',4,'#7582E6'),('시험',2,'#D48560'),('독서',1,'#CF779A')])
    assert height==18 and all(label.y()==0 for label in (badge.assignment,badge.movie,*badge.custom) if not label.isHidden())
    for text in ('과제 1건','영상 2건','운동 3건','할 일 4건','시험 2건','독서 1건'):assert text in badge.accessibleName()
    shown=[label for label in (badge.assignment,badge.movie,*badge.custom) if not label.isHidden()]
    assert len(shown)==3 and shown[-1].text().startswith('+') and shown[-1].geometry().right()<160
    badge.deleteLater();app.processEvents()

def test_keyboard_date_selection_updates_native_labels_and_selected_day(app,tmp_path):
    w=MainWindow(tmp_path);w.show();w.select_page(0);w.select_day(date(2026,11,29));w.main_stack._settle();app.processEvents();w.calendar.setFocus()
    QTest.keyClick(w.calendar.view,Qt.Key.Key_Right);app.processEvents()
    assert w.selected_date==date(2026,11,30)
    selected=[label.text() for label in w.calendar.date_labels if label.property('dayState')=='selected']
    assert selected==['30']
    w.dispose();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
