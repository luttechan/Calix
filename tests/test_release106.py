from datetime import date
import json,sqlite3,zipfile
import pytest
from PySide6.QtCore import Qt,QPoint,QCoreApplication,QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from learning_calendar.holidays import HolidayCalendar

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
