import json
import sqlite3
from pathlib import Path
import sys
import pytest
from learning_calendar.storage import Store
from learning_calendar.models import Course
from learning_calendar.local_backup import write_backup, read_backup, restore_backup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop"))
from engine_api import EngineAPI

def test_legacy_session_migrates_and_stays_editable(tmp_path):
    path = tmp_path / "learning.db"
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE timetable(id INTEGER PRIMARY KEY,course_id INTEGER,day INTEGER,start_time TEXT,end_time TEXT,professor TEXT,room TEXT)")
    db.execute("INSERT INTO timetable VALUES(7,1,2,'10:00','11:00','교수','A201')")
    db.commit(); db.close()
    store = Store(path)
    row = store.timetable()[0]
    assert row['title'] == '' and row['is_online'] == 0 and row['id'] == 7
    store.add_timetable(1,2,'10:00','11:00',item_id=7,title='편집한 이름')
    store.close()
    store = Store(path)
    assert store.timetable()[0]['title'] == '편집한 이름'
    store.close()

def test_online_custom_and_linked_classes_do_not_occupy_grid(tmp_path):
    api = EngineAPI(tmp_path)
    try:
        for title in ('기업가정신','온라인 세미나'):
            api.dispatch('timetable.save',dict(course_id=0,title=title,is_online=True))
        api.dispatch('timetable.save',dict(course_id=0,title='스터디',day=0,start_time='09:00',end_time='10:00'))
        rows = api.bootstrap()['sessions']
        assert len(rows) == 3
        assert all(r['start_time'] == r['end_time'] == '' for r in rows if r['is_online'])
        assert sum(r['is_online'] for r in rows) == 2
        assert api.bootstrap()['courses'] == []
    finally: api.close()

def test_edit_transition_checks_conflicts_without_losing_old_entry(tmp_path):
    store = Store(tmp_path/'learning.db')
    store.add_timetable(1,0,'09:00','10:00')
    item = store.add_timetable(0,0,'','',title='직접 추가',is_online=True)
    with pytest.raises(ValueError):
        store.add_timetable(0,0,'09:30','11:00',item_id=item,title='충돌')
    assert next(r for r in store.timetable() if r['id']==item)['is_online'] == 1
    store.add_timetable(0,1,'09:30','11:00',item_id=item,title='직접 추가')
    assert next(r for r in store.timetable() if r['id']==item)['is_online'] == 0
    store.close()

def test_sync_and_backup_preserve_custom_name_and_online_flag(tmp_path):
    store = Store(tmp_path/'learning.db')
    store.apply_batch([Course(1,'학교 강의명')],{(1,'assignment'):[]})
    store.add_timetable(1,0,'','',title='기업가정신',is_online=True,professor='담당 교수',color='#7582E6')
    store.add_timetable(0,1,'10:00','11:00',title='개인 스터디')
    store.apply_batch([Course(1,'동기화된 강의명')],{(1,'assignment'):[]})
    archive = tmp_path/'backup.calix'
    write_backup(archive,store,tmp_path)
    backup = read_backup(archive)
    restore_backup(backup,store,tmp_path)
    rows = store.timetable()
    assert {r['title'] for r in rows} == {'기업가정신','개인 스터디'}
    assert next(r for r in rows if r['is_online'])['professor'] == '담당 교수'
    store.close()

def test_invalid_custom_class_is_rejected(tmp_path):
    store = Store(tmp_path/'learning.db')
    with pytest.raises(ValueError):store.add_timetable(0,0,'09:00','10:00')
    with pytest.raises(ValueError):store.add_timetable(0,0,'','',title='수업',is_online='false')
    with pytest.raises(ValueError):store.add_timetable(0,0,'09:00','10:00',title='수업',item_id=999)
    assert store.timetable() == []
    store.close()

def test_release_versions_match():
    import tomllib
    from engine_updates import VERSION
    version = json.loads((ROOT/'desktop/package.json').read_text(encoding='utf-8'))['version']
    assert version == VERSION == '1.5.6'
    assert tomllib.loads((ROOT/'desktop/src-tauri/Cargo.toml').read_text())['package']['version'] == version
    assert json.loads((ROOT/'desktop/src-tauri/tauri.conf.json').read_text(encoding='utf-8'))['version'] == version
