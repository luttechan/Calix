import sqlite3,json
from datetime import datetime
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication,QDialog
from PySide6.QtCore import QCoreApplication,QEvent,QPoint
from learning_calendar.models import Course,Event,KST
from learning_calendar.storage import Store
from learning_calendar.paths import migrate_legacy_data,asset_path

@pytest.fixture(scope='module')
def app():return QApplication.instance() or QApplication([])


def test_old_timetable_schema_gets_color_without_losing_rows(tmp_path):
    path=tmp_path/'old.db';db=sqlite3.connect(path)
    db.execute("CREATE TABLE timetable(id INTEGER PRIMARY KEY,course_id INTEGER,day INTEGER,start_time TEXT,end_time TEXT,professor TEXT,room TEXT)")
    db.execute("INSERT INTO timetable VALUES(1,1,0,'09:00','10:00','교수','A201')");db.commit();db.close()
    store=Store(path);row=store.timetable()[0]
    assert row['color']=='' and row['room']=='A201' and row['professor']=='교수'
    store.set_timetable_color(1,'#459cd4');store.close();again=Store(path)
    assert again.timetable()[0]['color']=='#459CD4';again.close()





def test_data_migration_preserves_notes_colors_and_original(tmp_path):
    old=tmp_path/'legacy';old.mkdir();store=Store(old/'learning.db')
    e=Event('a',1,'과목','assignment','제목',None,False);store.apply_batch([Course(1,'과목')],{(1,'assignment'):[e]})
    store.set_note('a','보존할 메모');store.set_starred('a',True);store.add_timetable(1,0,'09:00','10:00',color='#CF779A');store.close()
    (old/'canvas_session.dpapi').write_bytes(b'synthetic-encrypted-data');(old/'settings.json').write_text(json.dumps({'theme':'mint'}))
    original=(old/'learning.db').read_bytes();target=tmp_path/'LutteLaurent/Calix'
    assert migrate_legacy_data(target,old);migrated=Store(target/'learning.db')
    assert migrated.events()[0].note=='보존할 메모' and migrated.events()[0].starred
    assert migrated.timetable()[0]['color']=='#CF779A';migrated.close()
    assert (old/'learning.db').read_bytes()==original
    assert (target/'canvas_session.dpapi').read_bytes()==b'synthetic-encrypted-data'
    assert not migrate_legacy_data(target,old)




def test_legacy_credentials_are_read_without_rewriting(monkeypatch):
    import keyring
    from learning_calendar.preferences import read_account,read_password
    values={('BUFS Learning Calendar','__account_id__'):'synthetic-id',('BUFS Learning Calendar/password','synthetic-id'):'synthetic-password'}
    monkeypatch.setattr(keyring,'get_password',lambda service,key:values.get((service,key)))
    monkeypatch.setattr(keyring,'set_password',lambda *args:pytest.fail('read must not rewrite secrets'))
    assert read_account()=='synthetic-id' and read_password('synthetic-id')=='synthetic-password'
