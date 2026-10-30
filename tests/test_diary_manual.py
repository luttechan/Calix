import json,sqlite3,zipfile
from datetime import datetime,timedelta
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QDate,Qt,QEventLoop,QTimer
from learning_calendar.diary_crypto import Vault,VaultError,new_material,unlock_material,wrap_key,wipe
from learning_calendar.diary_store import DiaryStore
from learning_calendar.storage import Store
from learning_calendar.models import KST,Course,Event
from learning_calendar.local_backup import write_backup,read_backup,restore_backup

PASSWORD='synthetic-long-passphrase-only'

@pytest.fixture(scope='module')
def app():return QApplication.instance() or QApplication([])

def test_secret_disk_has_no_title_date_or_body_and_nonce_changes(tmp_path):
    path=tmp_path/'private.db';vault=Vault(path);key,header=new_material(PASSWORD);vault.initialize(key,header);wipe(key)
    value=dict(date='2047-11-29',title='unique-secret-title-절대평문금지',body='고유비밀본문 synthetic secret 🗝️')
    item=vault.save(value);assert vault.read(item)==value
    first=vault.db.execute('SELECT nonce,cipher FROM entries').fetchone();vault.save(value,item)
    second=vault.db.execute('SELECT nonce,cipher FROM entries').fetchone();assert first[0]!=second[0] and first[1]!=second[1]
    vault.lock();assert vault.key is None
    with pytest.raises(VaultError):vault.read(item)
    with pytest.raises(VaultError):unlock_material(vault.header(),'wrong-password')
    key=unlock_material(vault.header(),PASSWORD);vault.activate(key);wipe(key);assert vault.read(item)==value
    raw=path.read_bytes()
    for secret in (*value.values(),PASSWORD):assert secret.encode('utf-8') not in raw
    vault.close()

def test_tamper_record_swap_and_password_change(tmp_path):
    vault=Vault(tmp_path/'v.db');key,header=new_material(PASSWORD);vault.initialize(key,header)
    a=vault.save(dict(date='2026-10-27',title='first',body='secret'));b=vault.save(dict(date='2026-10-28',title='second',body='other'))
    nonce,cipher=vault.db.execute('SELECT nonce,cipher FROM entries WHERE id=?',(a,)).fetchone()
    with vault.db:vault.db.execute('UPDATE entries SET nonce=?,cipher=? WHERE id=?',(nonce,cipher,b))
    with pytest.raises(VaultError):vault.read(b)
    old_header=vault.header();new_password='new-very-long-password';vault.replace_header(wrap_key(new_password,key));wipe(key);vault.lock()
    with pytest.raises(VaultError):unlock_material(vault.header(),PASSWORD)
    key=unlock_material(vault.header(),new_password);vault.activate(key);wipe(key);assert vault.read(a)['body']=='secret'
    key=unlock_material(old_header,PASSWORD);wipe(key);vault.close()



def test_recurring_month_end_atomic_validation_and_undo(tmp_path):
    store=Store(tmp_path/'learning.db');tid=store.event_types()[0]['id']
    keys=store.create_manual_events(dict(title='월말 정리',type_id=tid,due_at='2027-01-31T20:00:00+09:00'),'monthly',3)
    assert [event.due.strftime('%m-%d') for event in store.events()]==['01-31','02-28','03-31']
    assert len({event.series_id for event in store.events()})==1
    old=store.manual_snapshot(keys);store.remove_manual_event(keys[0],True);assert store.events()==[]
    store.restore_manual_snapshot(old);assert len(store.events())==3
    with pytest.raises(ValueError):store.create_manual_events(dict(title='bad',type_id=tid),'daily',3)
    assert len(store.events())==3
    # An overflow in a later occurrence must also roll back the first insertion.
    with pytest.raises((ValueError,OverflowError)):store.create_manual_events(dict(title='overflow',type_id=tid,due_at='9999-12-31T20:00:00+09:00'),'daily',3)
    assert len(store.events())==3;store.close()

def test_backup_roundtrip_never_decrypts_secret_and_rejects_invalid_input(tmp_path):
    store=Store(tmp_path/'learning.db');store.set_meta('canvas_user_id','123');store.apply_batch([Course(1,'테스트 과목')],{(1,'assignment'):[]})
    tid=store.save_event_type('운동','#3AA68E');store.save_manual_event('걷기',tid,note='일정 메모');store.add_timetable(1,2,'10:15','11:00',color='#7582E6')
    normal=DiaryStore(tmp_path/'journals.db');normal.save(dict(date='2026-10-27',title='일반',body='normal diary'));normal.close()
    vault=Vault(tmp_path/'private-diary.db');key,header=new_material(PASSWORD);vault.initialize(key,header);wipe(key)
    secret_id=vault.save(dict(date='2026-10-27',title='secret unique title',body='secret unique body'));vault.close()
    archive=tmp_path/'backup.calix';write_backup(archive,store,tmp_path);value=read_backup(archive,'123')
    with zipfile.ZipFile(archive) as z:raw=z.read('calix.json');assert b'secret unique title' not in raw and b'secret unique body' not in raw and PASSWORD.encode() not in raw
    with pytest.raises(ValueError):read_backup(archive,'456')
    store.save_manual_event('추가',tid);restore_backup(value,store,tmp_path);assert [e.title for e in store.events()]==['걷기'] and store.timetable()[0]['color']=='#7582E6'
    restored=Vault(tmp_path/'private-diary.db');key=unlock_material(restored.header(),PASSWORD);restored.activate(key);wipe(key);assert restored.read(secret_id)['body']=='secret unique body';restored.close()
    value['schedule']['timetable'][0]['end_time']='09:00'
    with zipfile.ZipFile(archive,'w') as z:z.writestr('calix.json',json.dumps(value))
    with pytest.raises(ValueError):read_backup(archive,'123')
    store.close()




def test_backup_restore_rolls_back_all_databases_on_failure(tmp_path):
    store=Store(tmp_path/'learning.db');tid=store.event_types()[0]['id'];store.save_manual_event('기존 일정',tid)
    diary=DiaryStore(tmp_path/'journals.db');diary.save(dict(date='2026-10-27',title='old diary',body='original'));diary.close()
    archive=tmp_path/'b.calix';write_backup(archive,store,tmp_path);value=read_backup(archive)
    value['schedule']['events'][0]['title']='changed';value['journals'][0]['body']='changed'
    db=sqlite3.connect(tmp_path/'journals.db');db.execute("CREATE TRIGGER fail_insert BEFORE INSERT ON entries BEGIN SELECT RAISE(ABORT,'synthetic disk failure'); END");db.commit();db.close()
    with pytest.raises(sqlite3.Error):restore_backup(value,store,tmp_path)
    assert store.events()[0].title=='기존 일정'
    diary=DiaryStore(tmp_path/'journals.db');assert diary.summaries()[0]['title']=='old diary' and diary.read(diary.summaries()[0]['id'])['body']=='original';diary.close();store.close()

