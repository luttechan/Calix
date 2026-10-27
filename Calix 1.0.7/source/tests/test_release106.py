from datetime import date
import json,sqlite3,zipfile
import pytest
from PySide6.QtCore import Qt,QPoint,QCoreApplication,QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from learning_calendar.holidays import HolidayCalendar
from learning_calendar.special_dates_dialog import SpecialDatesDialog

@pytest.fixture(scope='module')
def app():return QApplication.instance() or QApplication([])

def test_mystery_independent_annual_date_and_restart(tmp_path):
    path=tmp_path/'holidays.db';cal=HolidayCalendar(path)
    assert not cal.birthday_enabled and cal.special_dates(2026)=={}
    cal.set_birthday(True)
    for year in (2026,2027,2030):assert cal.special_dates(year)[date(year,6,27)]=='클로네 생일'
    assert not cal.catholic_enabled and date(2026,6,27) not in cal.year(2026)
    cal.set_catholic(True);assert cal.special_dates(2026)[date(2026,6,27)].startswith('클로네 생일 / ')
    cal.set_catholic(False);cal.close();cal=HolidayCalendar(path)
    assert cal.birthday_enabled and cal.special_dates(2027)[date(2027,6,27)]=='클로네 생일'
    cal.set_birthday(False);assert cal.special_dates(2027)=={};cal.close()

def test_menu_path_and_mystery_updates_calendar_without_task_counts(app,tmp_path):
    from learning_calendar.gui import MainWindow
    from learning_calendar.holiday_dialog import HolidayDialog
    w=MainWindow(tmp_path);w.resize(1360,900);w.show();w.select_page(0);w.main_stack._settle();w.select_day(date(2026,6,27));app.processEvents()
    settings=next(action.menu() for action in w.menuBar().actions() if action.text()=='설정')
    other=next(action.menu() for action in settings.actions() if action.text()=='기타')
    action=next(action for action in other.actions() if action.text()=='특수 일정 등록')
    dialogs=[];w._exec_dialog=lambda dialog:dialogs.append(dialog)
    action.trigger();dialog=dialogs[0];assert isinstance(dialog,SpecialDatesDialog)
    assert dialog.catholic.text()=='가톨릭 일정' and dialog.mystery.text()=='???'
    dialog.show();app.processEvents();before=w.snapshot.deadline_counts()
    QTest.mouseClick(dialog.mystery,Qt.MouseButton.LeftButton,pos=QPoint(8,dialog.mystery.height()//2));app.processEvents();w.calendar._layout_badges()
    assert w.day_feast.text()=='클로네 생일' and w.snapshot.deadline_counts()==before
    birthday=next(label for label in w.calendar.feast_labels if label.property('calendarDate')=='2026-06-27')
    assert birthday.isVisible() and birthday.toolTip()=='클로네 생일'
    w.set_theme('dark');app.processEvents();assert birthday.isVisible()
    w.select_day(date(2027,6,27));app.processEvents();assert w.day_feast.text()=='클로네 생일'
    QTest.mouseClick(dialog.mystery,Qt.MouseButton.LeftButton,pos=QPoint(8,dialog.mystery.height()//2));app.processEvents();assert not w.day_feast.isVisible()
    holiday=HolidayDialog(w.holiday_calendar,w.selected_date,w);assert not hasattr(holiday,'catholic')
    holiday.deleteLater();dialog.close();dialog.deleteLater();w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

def test_failed_toggle_keeps_saved_value(app,tmp_path,monkeypatch):
    cal=HolidayCalendar(tmp_path/'holidays.db');dialog=SpecialDatesDialog(cal)
    def fail(value):raise sqlite3.OperationalError('test')
    monkeypatch.setattr(cal,'set_birthday',fail);dialog.mystery.setChecked(True)
    assert not dialog.mystery.isChecked() and not cal.birthday_enabled and '저장하지 못했습니다' in dialog.status.text()
    dialog.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);cal.close()

def test_special_option_backup_restore_and_legacy_preservation(tmp_path):
    from learning_calendar.storage import Store
    from learning_calendar.local_backup import write_backup,read_backup,restore_backup
    store=Store(tmp_path/'learning.db');cal=HolidayCalendar(tmp_path/'holidays.db');cal.set_birthday(True)
    path=tmp_path/'backup.calix';write_backup(path,store,tmp_path);value=read_backup(path)
    assert value['holiday_preferences']['klone_birthday'] is True
    cal.set_birthday(False);restore_backup(value,store,tmp_path);cal.reload();assert cal.birthday_enabled
    del value['holiday_preferences']['klone_birthday'];restore_backup(value,store,tmp_path);cal.reload();assert cal.birthday_enabled
    value['holiday_preferences']['klone_birthday']='false'
    with zipfile.ZipFile(path,'w') as archive:archive.writestr('calix.json',json.dumps(value))
    with pytest.raises(ValueError):read_backup(path)
    cal.close();store.close()
