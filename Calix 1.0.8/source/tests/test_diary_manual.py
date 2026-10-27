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
from learning_calendar.reminders import DueReminders

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

def test_diary_lock_clears_editor_metadata_and_pending_saves(app,tmp_path):
    from learning_calendar.diary_view import DiaryPage
    page=DiaryPage(tmp_path);page.new_entry();page.title.setText('normal');page.body.setPlainText('일반 본문');assert page.flush()
    normal_id=page.current_id;page.set_secret(True);key,header=new_material(PASSWORD);page.vault.initialize(key,header);wipe(key)
    page.stack.setCurrentWidget(page.workspace);page.new_entry();page.title.setText('비밀 제목');page.body.setPlainText('비밀 본문');secret_id=page.current_id
    page.lock()
    assert page.vault.key is None and not page.title.text() and not page.body.toPlainText() and not page.metadata and page.entries.count()==0
    key=unlock_material(page.vault.header(),PASSWORD);page.vault.activate(key);wipe(key);assert page.vault.read(secret_id)['body']=='비밀 본문'
    assert page.normal.read(normal_id)['body']=='일반 본문'
    page.set_secret(False);assert page.body.isUndoRedoEnabled();page.shutdown();page.deleteLater();app.processEvents()

def test_async_unlock_and_stale_results_cannot_reopen_locked_vault(app,tmp_path):
    from learning_calendar.diary_view import DiaryPage
    page=DiaryPage(tmp_path);page.set_secret(True);page.password.setText(PASSWORD);page.confirm.setText(PASSWORD);page.unlock()
    loop=QEventLoop();page.work_finished.connect(loop.quit);QTimer.singleShot(6000,loop.quit);loop.exec()
    assert page.task is None and page.vault.initialized and page.vault.unlocked
    page.lock();page.password.setText(PASSWORD);page.unlock();page.lock();loop.exec()
    assert page.task is None and not page.vault.unlocked
    page.shutdown();page.deleteLater();app.processEvents()

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

def test_reminders_deduplicate_skip_past_and_follow_due_date_changes():
    now=datetime(2026,10,27,10,tzinfo=KST);r=DueReminders()
    def row(key,delta,done=False):return Event(key,1,'과목','manual',key,(now+timedelta(minutes=delta)).isoformat(),done)
    events=[row('past',-1),row('soon',5),row('later',20),row('done',4,True)]
    assert [e.key for e in r.pending(events,now)]==['soon'];assert r.pending(events,now)==[]
    assert [e.key for e in r.pending([row('soon',8)],now)]==['soon']

def test_manual_dialog_recurrence_and_type_filters(app,tmp_path):
    from learning_calendar.gui import MainWindow
    from learning_calendar.manual_events import ManualEventDialog
    w=MainWindow(tmp_path);tid=w.store.save_event_type('운동','#3AA68E');w.store.save_manual_event('걷기',tid,due_at=datetime.now(KST).replace(hour=23,minute=59).isoformat());w._reload()
    d=ManualEventDialog(w.store,[]);d.show();app.processEvents();d.repeat.setCurrentIndex(2);assert d.repeat_count.isEnabled();d.no_due.setChecked(True);assert not d.repeat_count.isEnabled() and d.repeat.currentData()=='none'
    w.type_filter.setCurrentIndex(w.type_filter.findData(f'type:{tid}'));assert [e.title for e in w._filtered]==['걷기']
    event=w.store.events()[0];w.complete_manual(event,True);assert w.store.events()[0].completed;w.undo_manual();assert not w.store.events()[0].completed
    w.show_diary();w.main_stack._settle();assert w.main_stack.currentIndex()==2 and w.diary is not None
    d.close();d.deleteLater();w.dispose();w.deleteLater();app.processEvents()

def test_rich_diary_format_survives_save_reopen_and_encryption(app,tmp_path):
    from learning_calendar.diary_view import DiaryPage
    from PySide6.QtGui import QTextCursor,QTextCharFormat,QColor,QFont
    page=DiaryPage(tmp_path);page.new_entry();page.body.setPlainText('굵고 기울어진 색깔 글씨')
    cursor=page.body.textCursor();cursor.select(QTextCursor.SelectionType.Document);page.body.setTextCursor(cursor)
    page.format_bar.toggle('bold',True);page.format_bar.toggle('italic',True);page.format_bar.toggle('underline',True)
    fmt=QTextCharFormat();fmt.setForeground(QColor('#CF779A'));page.format_bar.merge(fmt);assert page.flush()
    value=page.normal.read(page.current_id);assert 'font-weight:700' in value['html'] and 'font-style:italic' in value['html'] and '#cf779a' in value['html']
    key,header=new_material(PASSWORD);page.set_secret(True);page.vault.initialize(key,header);wipe(key)
    secret_id=page.vault.save(value);page.lock();key=unlock_material(page.vault.header(),PASSWORD);page.vault.activate(key);wipe(key)
    restored=page.vault.read(secret_id);page.body.setHtml(restored['html']);cursor=page.body.textCursor();cursor.setPosition(1);page.body.setTextCursor(cursor)
    assert page.body.currentCharFormat().fontWeight()==QFont.Weight.Bold and page.body.currentCharFormat().fontItalic()
    assert value['html'].encode() not in (tmp_path/'private-diary.db').read_bytes()
    page.shutdown();page.deleteLater();app.processEvents()

def test_backup_restore_rolls_back_all_databases_on_failure(tmp_path):
    store=Store(tmp_path/'learning.db');tid=store.event_types()[0]['id'];store.save_manual_event('기존 일정',tid)
    diary=DiaryStore(tmp_path/'journals.db');diary.save(dict(date='2026-10-27',title='old diary',body='original'));diary.close()
    archive=tmp_path/'b.calix';write_backup(archive,store,tmp_path);value=read_backup(archive)
    value['schedule']['events'][0]['title']='changed';value['journals'][0]['body']='changed'
    db=sqlite3.connect(tmp_path/'journals.db');db.execute("CREATE TRIGGER fail_insert BEFORE INSERT ON entries BEGIN SELECT RAISE(ABORT,'synthetic disk failure'); END");db.commit();db.close()
    with pytest.raises(sqlite3.Error):restore_backup(value,store,tmp_path)
    assert store.events()[0].title=='기존 일정'
    diary=DiaryStore(tmp_path/'journals.db');assert diary.summaries()[0]['title']=='old diary' and diary.read(diary.summaries()[0]['id'])['body']=='original';diary.close();store.close()

def test_native_time_and_count_editors_keep_visible_text_area(app,tmp_path):
    from learning_calendar.manual_events import ManualEventDialog
    from learning_calendar.design import stylesheet
    store=Store(tmp_path/'learning.db');dialog=ManualEventDialog(store,[]);dialog.setStyleSheet(stylesheet());dialog.show();app.processEvents()
    assert dialog.time.lineEdit().width()>=dialog.time.fontMetrics().horizontalAdvance('23:59')
    dialog.repeat.setCurrentIndex(1);assert dialog.repeat_count.lineEdit().width()>30
    dialog.time.step_minutes(15);assert dialog.time.time().toString('HH:mm')=='23:59'
    dialog.time.step_minutes(-15);assert dialog.time.time().toString('HH:mm')=='23:44'
    dialog.close();dialog.deleteLater();app.processEvents();store.close()
