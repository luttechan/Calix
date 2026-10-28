from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
import pytest
from learning_calendar.models import Event, Course, KST, deadline_display
from learning_calendar.storage import Store
from learning_calendar.preferences import read_settings, write_settings


def make_event(due, completed=False, kind='assignment'):
    return Event('assignment:10:7', 10, '원래 긴 이름', kind, '과제', due.isoformat() if due else None, completed)


@pytest.mark.parametrize('delta,color,fragment', [
    (timedelta(days=9),'green','9일'),
    (timedelta(days=7),'orange','7일'),
    (timedelta(days=2),'orange','2일'),
    (timedelta(days=1,hours=23),'red','1일'),
    (timedelta(hours=23),'red','23시간'),
    (timedelta(minutes=20),'red','20분'),
])
def test_dynamic_deadline_label(delta,color,fragment):
    now=datetime(2026,10,11,10,0,tzinfo=KST)
    status,c=deadline_display(make_event(now+delta),now)
    assert c==color
    assert fragment in status


def test_complete_never_overdue():
    now=datetime(2026,10,11,10,0,tzinfo=KST)
    e=make_event(now-timedelta(days=5),True)
    assert e.status(now)=='완료'
    assert deadline_display(e,now)==('완료','done')
    assert deadline_display(make_event(now-timedelta(days=2)),now)==('기한 경과','red')


def test_alias_sync_preserves_name(tmp_path):
    store=Store(tmp_path/'db.sqlite3')
    c=Course(101,'매우매우긴과목')
    e=make_event(datetime(2026,10,13,10,0,tzinfo=KST))
    e.course_id=101;e.key='assignment:101:7';e.course_name=c.name
    store.apply_batch([c], {(101,'assignment'):[e]})
    store.set_alias(101,'짧은 이름')
    assert store.courses()[0].name=='짧은 이름'
    assert store.events()[0].course_name=='짧은 이름'
    store.apply_batch([Course(101,'변경된 원래 이름')],{(101,'assignment'):[e]})
    assert store.events()[0].course_name=='짧은 이름'
    store.close()


def test_timetable_edit_delete_and_collision(tmp_path):
    store=Store(tmp_path/'db.sqlite3')
    store.apply_batch([Course(1,'일어'),Course(2,'영어')],{})
    store.add_timetable(1,0,'09:00','10:30','박 교수','A201')
    with pytest.raises(ValueError):
        store.add_timetable(2,0,'10:00','12:00')
    store.add_timetable(2,2,'10:00','12:00','김 교수','A301')
    first=store.timetable()[0]
    assert first['professor']=='박 교수'
    store.add_timetable(1,0,'09:30','11:00','박 교수','B201',item_id=first['id'])
    assert store.timetable()[0]['room']=='B201'
    store.remove_timetable(first['id'])
    assert len(store.timetable())==1
    store.close()


def test_migrate_old_database(tmp_path):
    path=tmp_path/'old.db'
    con=sqlite3.connect(path)
    con.execute('CREATE TABLE courses (id INTEGER PRIMARY KEY,name TEXT NOT NULL)')
    con.execute("INSERT INTO courses VALUES(10,'일본어')")
    con.commit();con.close()
    store=Store(path)
    store.set_alias(10,'일어')
    assert store.courses()[0].name=='일어'
    store.close()


def test_settings_do_not_write_account(tmp_path):
    cfg=tmp_path/'config.json'
    write_settings(cfg,{'student_id':'1234','password':'do-not-write','window_width':1111})
    data=cfg.read_text(encoding='utf-8')
    assert '1234' not in data and 'password' not in data
    assert read_settings(cfg)['window_width']==1111
