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

def test_mixed_completed_assignments_fade_only_completed_badges(app):
    from learning_calendar.calendar_view import DayBadges
    row=Event('assignment:1:1',1,'과목','assignment','미완료','2026-11-02T23:59:00+09:00',False);done=replace(row,key='assignment:1:2',title='완료',completed=True)
    badge=DayBadges();badge.resize(300,22);badge.set_events(date(2026,11,2),[row,done]);badge.configure(1,0,300,22,assignment_done=1);badge.show();app.processEvents()
    assert badge.assignment.property('calendarOpacity')==1 and badge.assignment_done.property('calendarOpacity')==.38
    assert badge.assignment_done.graphicsEffect() is None and badge.matching(badge.assignment_done)==[done] and badge.matching(badge.assignment)==[row]
    calls=[];badge.details_requested.connect(lambda *args:calls.append(args));QTest.mouseClick(badge.assignment_done,Qt.MouseButton.LeftButton);assert calls[-1][1]==[done]
    badge.configure(1,0,300,22);assert badge.assignment_done.isHidden() and badge.assignment.property('calendarOpacity')==1
    badge.close();badge.deleteLater()

def test_custom_assignment_completion_fade_and_overflow_preserve_every_row(app):
    from learning_calendar.calendar_view import DayBadges
    badge=DayBadges();row=Event('assignment:1:1',1,'과목','assignment','완료','2026-11-02T23:59:00+09:00',True,type_id=1,type_name='발표',type_color='#7582E6')
    badge.set_events(date(2026,11,2),[row]);badge.configure(0,0,300,22,[('발표',1,'#7582E6',True)])
    assert badge.custom[0].property('calendarOpacity')==.38 and badge.matching(badge.custom[0])==[row]
    badge.configure(1,1,100,22,[('발표',1,'#7582E6',True),('시험',2,'#D48560',False),('회의',1,'#CF779A',False),('운동',1,'#3AA68E',False)],assignment_done=2)
    assert '완료 과제 2건' in badge.accessibleName() and '운동 1건' in badge.accessibleName() and badge.matching(badge.custom[2])==[row];badge.deleteLater()

def test_calendar_holiday_is_visible_without_tasks_and_detail_button_is_constant(app,tmp_path):
    from learning_calendar.gui import MainWindow
    w=MainWindow(tmp_path);w.resize(1360,900);w.holiday_calendar.save('2026-11-02','임시공휴일');w.select_page(0);w.select_day(date(2026,11,2));w.main_stack._settle();w.show();app.processEvents();w.calendar._layout_badges()
    label=next(h for h in w.calendar.holiday_labels if h.property('calendarDate')=='2026-11-02')
    assert label.isVisible() and label.text()=='임시공휴일' and w.day_holiday.text()=='임시공휴일' and w.day_toggle.text()=='상세 일정'
    w.type_filter.setCurrentIndex(w.type_filter.findData('movie'));w.state_select.setCurrentIndex(2);w.refresh();app.processEvents();assert label.isVisible()
    w.set_theme('dark');app.processEvents();w.calendar._layout_badges();assert label.isVisible() and w.calendar.holidays[date(2026,11,2)]=='임시공휴일'
    w.shift_month(1);assert w.day_toggle.text()=='상세 일정'
    w.dispose();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

def test_holiday_dialog_manual_save_hide_reset_and_year_change(app,tmp_path):
    from learning_calendar.holiday_dialog import HolidayDialog
    cal=HolidayCalendar(tmp_path/'holidays.db');dialog=HolidayDialog(cal,date(2026,11,2));dialog.show();app.processEvents();dialog.name.setText('임시공휴일');dialog.save_entry();assert date(2026,11,2) in cal.year(2026)
    dialog.enabled.setChecked(False);dialog.save_entry();assert date(2026,11,2) not in cal.year(2026)
    dialog.reset_entry();assert '2026-11-02' not in cal.overrides
    dialog.day.setDate(QDate(2028,2,29));dialog.year.setCurrentIndex(dialog.year.findData(2027));assert dialog.day.date()==QDate(2027,2,28)
    dialog.close();dialog.deleteLater();app.processEvents();cal.close()

def test_transition_snapshot_memory_is_bounded_on_large_windows(app,tmp_path):
    from learning_calendar.gui import MainWindow
    w=MainWindow(tmp_path);w.resize(2500,1600);w.show();app.processEvents();w.select_page(0)
    assert w.main_stack._overlay is None and w.main_stack._group is not None
    w.main_stack._settle();assert w.main_stack._group is None
    w.dispose();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

def test_catholic_option_is_off_by_default_includes_saints_and_persists(tmp_path):
    path=tmp_path/'holidays.db';cal=HolidayCalendar(path);assert not cal.catholic_enabled and cal.feasts(2026)=={}
    cal.set_catholic(True);feasts=cal.feasts(2026)
    assert '주님 부활 대축일' in feasts[date(2026,4,5)] and '성 요한 바오로 2세' in feasts[date(2026,10,22)]
    assert any('기념일' in value for value in feasts.values()) and len(feasts)>150
    assert date(2026,4,5) not in cal.year(2026) and date(2026,10,22) not in cal.year(2026)
    assert '주님 승천' in cal.feasts(2027)[date(2027,5,9)] and '성체 성혈' in cal.feasts(2027)[date(2027,5,30)]
    cal.close();cal=HolidayCalendar(path);assert cal.catholic_enabled;cal.set_catholic(False);assert cal.feasts(2026)=={} and catholic_baseline.cache_info().currsize==0;cal.close()

def test_catholic_labels_are_separate_lazy_and_survive_theme_change(app,tmp_path):
    from learning_calendar.gui import MainWindow
    from learning_calendar.special_dates_dialog import SpecialDatesDialog
    w=MainWindow(tmp_path);w.resize(1360,900);w.select_page(0);w.select_day(date(2026,10,22));w.main_stack._settle();w.show();app.processEvents();assert w.calendar.feast_labels==[]
    dialog=SpecialDatesDialog(w.holiday_calendar,w);dialog.changed.connect(w.refresh);dialog.catholic.setChecked(True);app.processEvents();w.calendar._layout_badges()
    day_label=next(label for label in w.calendar.feast_labels if label.property('calendarDate')=='2026-10-22');assert day_label.isVisible() and '요한 바오로 2세' in day_label.toolTip() and day_label.textFormat()==Qt.TextFormat.PlainText
    w.set_theme('dark');app.processEvents();assert day_label.isVisible() and '요한 바오로 2세' in w.day_feast.text()
    dialog.catholic.setChecked(False);app.processEvents();assert not day_label.isVisible() and not w.day_feast.isVisible()
    dialog.close();dialog.deleteLater();w.dispose();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

def test_calendar_does_not_keep_a_year_of_offscreen_date_formats(app,tmp_path):
    from learning_calendar.calendar_view import MonthCanvas
    cal=HolidayCalendar(tmp_path/'holidays.db');cal.set_catholic(True);view=MonthCanvas();view.set_month(date(2026,10,1),date(2026,10,22),{},cal.year(2026),cal.feasts(2026))
    assert view.dateTextFormat(QDate(2026,10,22)).toolTip() and not view.dateTextFormat(QDate(2026,1,1)).toolTip()
    view.set_month(date(2026,1,1),date(2026,1,1),{},cal.year(2026),cal.feasts(2026));assert view.dateTextFormat(QDate(2026,1,1)).toolTip() and not view.dateTextFormat(QDate(2026,10,22)).toolTip()
    view.deleteLater();cal.close()


def test_repeated_memory_sampling_does_not_accumulate_native_counter_types():
    import gc,sys
    from learning_calendar import diagnostics
    if sys.platform!='win32':pytest.skip('Windows process counters')
    def counter_types():
        return sum(isinstance(obj,type) and obj.__name__=='COUNTERS' and obj.__module__==diagnostics.__name__ for obj in gc.get_objects())
    assert diagnostics.memory_usage()['working_set_mb']>0
    before=counter_types()
    for _ in range(200):diagnostics.memory_usage()
    gc.collect();assert counter_types()==before
