import json,zipfile
from dataclasses import replace
from datetime import datetime,timedelta
import pytest
from PySide6.QtCore import QPoint,QRect,QSize,Qt,QCoreApplication,QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from learning_calendar.models import Course,Event,KST
from learning_calendar.storage import Store
from learning_calendar.snapshot import Snapshot
from learning_calendar.local_backup import write_backup,read_backup,restore_backup

@pytest.fixture(scope='module')
def app():return QApplication.instance() or QApplication([])

def imported():return Event('assignment:1:99',1,'과목','assignment','학교 이름',(datetime.now(KST)+timedelta(days=2)).isoformat(),False)

def test_local_edits_survive_sync_archive_reopen_and_source_changes(tmp_path):
    path=tmp_path/'learning.db';store=Store(path);event=imported();courses=[Course(1,'과목')]
    store.apply_batch(courses,{(1,'assignment'):[event]});tid=store.save_event_type('발표','#7582E6')
    store.save_event_details(event.key,'나의 발표',tid,'지워지면 안 되는 메모')
    changed=replace(event,title='변경된 학교 이름',due_at='2030-11-29T23:59:00+09:00',completed=True)
    store.apply_batch(courses,{(1,'assignment'):[]});assert not store.events()
    with pytest.raises(ValueError):store.remove_event_type(tid)
    store.apply_batch(courses,{(1,'assignment'):[changed]});store.close();store=Store(path);row=store.events()[0]
    assert (row.title,row.type_id,row.note,row.source_title,row.due_at,row.completed)==('나의 발표',tid,'지워지면 안 되는 메모',changed.title,changed.due_at,True)
    raw=store.db.execute('SELECT title,kind FROM events').fetchone();assert tuple(raw)==(changed.title,'assignment')
    snap=Snapshot([row]);assert snap.filtered(type_key=f'type:{tid}')==[row] and snap.filtered(query=changed.title)==[row]
    store.save_event_details(row.key,changed.title,None,'');assert store.events()[0].title==changed.title and store.events()[0].type_id is None
    store.apply_batch(courses,{(1,'assignment'):[replace(changed,title='새 원본')]});assert store.events()[0].title=='새 원본';store.close()

def test_backup_roundtrip_and_legacy_preserve_edited_names_and_types(tmp_path):
    store=Store(tmp_path/'learning.db');event=imported();store.apply_batch([Course(1,'과목')],{(1,'assignment'):[event]})
    tid=store.save_event_type('발표','#7582E6');store.save_event_details(event.key,'직접 쓴 이름',tid,'메모')
    path=tmp_path/'backup.calix';write_backup(path,store,tmp_path);value=read_backup(path);assert value['version']==4
    store.save_event_details(event.key,'다른 이름',None,'');restore_backup(value,store,tmp_path);assert store.events()[0].title=='직접 쓴 이름'
    legacy=json.loads(json.dumps(value));legacy['version']=1;del legacy['schedule']['customizations'];legacy['schedule']['types']=[dict(id=tid,name='충돌 유형',color='#7582E6')]
    restore_backup(legacy,store,tmp_path);row=store.events()[0];assert (row.title,row.type_label,row.note)==('직접 쓴 이름','발표','메모')
    value['schedule']['customizations'][0]['event_key']='invalid'
    with zipfile.ZipFile(path,'w') as z:z.writestr('calix.json',json.dumps(value))
    with pytest.raises(ValueError):read_backup(path)
    store.close()





