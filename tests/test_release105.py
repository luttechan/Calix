from dataclasses import replace
from datetime import date,datetime,timedelta
import json,zipfile
import pytest
from PySide6.QtCore import Qt,QDate,QPoint,QCoreApplication,QEvent,QRect
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from learning_calendar.holidays import HolidayCalendar,baseline,catholic_baseline
from learning_calendar.models import Event,Course,KST
from learning_calendar.storage import Store
from learning_calendar.local_backup import write_backup,read_backup,restore_backup

@pytest.fixture(scope='module')
def app():return QApplication.instance() or QApplication([])

def test_baseline_lunar_substitute_and_current_2026_2027_changes(tmp_path):
    cal=HolidayCalendar(tmp_path/'holidays.db');y=cal.year(2026)
    for day in ('2026-02-16','2026-02-17','2026-02-18','2026-03-02','2026-05-01','2026-05-24','2026-05-25','2026-06-03','2026-07-17','2026-08-17','2026-09-25','2026-10-05'):assert date.fromisoformat(day) in y
    assert y[date(2026,5,1)]=='노동절' and y[date(2026,7,17)]=='제헌절'
    assert y[date(2026,2,16)]==y[date(2026,2,18)]=='설날 연휴' and y[date(2026,9,24)]==y[date(2026,9,26)]=='추석 연휴'
    assert y[date(2026,12,25)]=='크리스마스'
    y=cal.year(2027);assert '대체' in y[date(2027,5,3)] and '대체' in y[date(2027,7,19)]
    assert '2025-01-27' in baseline()['years']['2025'] and not cal.has_year(2051)
    assert all('·' not in name for year in baseline()['years'].values() for name in year.values());cal.close()

def test_holiday_overrides_persist_disable_reset_and_survive_canvas_sync(tmp_path):
    path=tmp_path/'holidays.db';cal=HolidayCalendar(path);cal.save('2026-11-02','임시공휴일');cal.save('2026-12-25','표시하지 않을 성탄절',False)
    assert cal.year(2026)[date(2026,11,2)]=='임시공휴일' and date(2026,12,25) not in cal.year(2026)
    store=Store(tmp_path/'learning.db');store.apply_batch([Course(1,'과목')],{(1,'assignment'):[]});store.close();cal.close()
    cal=HolidayCalendar(path);assert cal.year(2026)[date(2026,11,2)]=='임시공휴일'
    cal.reset('2026-12-25');cal.reset('2026-11-02');assert date(2026,12,25) in cal.year(2026) and date(2026,11,2) not in cal.year(2026)
    with pytest.raises(ValueError):cal.save('2026-02-30','없는 날')
    with pytest.raises(ValueError):cal.save('2026-01-01','  ')
    cal.close()

def test_holiday_backup_roundtrip_legacy_preservation_and_invalid_dates(tmp_path):
    store=Store(tmp_path/'learning.db');cal=HolidayCalendar(tmp_path/'holidays.db');cal.save('2026-11-02','임시');cal.save('2026-12-25','성탄절',False)
    cal.set_catholic(True);path=tmp_path/'backup.calix';write_backup(path,store,tmp_path);value=read_backup(path);assert len(value['holiday_overrides'])==2 and value['holiday_preferences']['catholic'] is True
    cal.save('2026-11-03','추가');cal.set_catholic(False);restore_backup(value,store,tmp_path);cal.reload();assert date(2026,11,3) not in cal.year(2026) and date(2026,12,25) not in cal.year(2026) and cal.catholic_enabled
    legacy=json.loads(json.dumps(value));legacy['version']=2;del legacy['holiday_overrides'];del legacy['holiday_preferences'];cal.save('2026-11-03','유지');restore_backup(legacy,store,tmp_path);cal.reload();assert date(2026,11,3) in cal.year(2026) and cal.catholic_enabled
    value['holiday_overrides'][0]['day']='2026-02-30'
    with zipfile.ZipFile(path,'w') as z:z.writestr('calix.json',json.dumps(value))
    with pytest.raises(ValueError):read_backup(path)
    cal.close();store.close()






def test_catholic_option_is_off_by_default_includes_saints_and_persists(tmp_path):
    path=tmp_path/'holidays.db';cal=HolidayCalendar(path);assert not cal.catholic_enabled and cal.feasts(2026)=={}
    cal.set_catholic(True);feasts=cal.feasts(2026)
    assert '주님 부활 대축일' in feasts[date(2026,4,5)] and '성 요한 바오로 2세' in feasts[date(2026,10,22)]
    assert any('기념일' in value for value in feasts.values()) and len(feasts)>150
    assert date(2026,4,5) not in cal.year(2026) and date(2026,10,22) not in cal.year(2026)
    assert '주님 승천' in cal.feasts(2027)[date(2027,5,9)] and '성체 성혈' in cal.feasts(2027)[date(2027,5,30)]
    cal.close();cal=HolidayCalendar(path);assert cal.catholic_enabled;cal.set_catholic(False);assert cal.feasts(2026)=={} and catholic_baseline.cache_info().currsize==0;cal.close()




