import sqlite3,json
from datetime import datetime
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication,QDialog
from PySide6.QtCore import QCoreApplication,QEvent,QPoint
from learning_calendar.gui import MainWindow
from learning_calendar.models import Course,Event,KST
from learning_calendar.storage import Store
from learning_calendar.paths import migrate_legacy_data,asset_path
from learning_calendar.timetable_view import SessionEditor,WeekSurface

@pytest.fixture(scope='module')
def app():return QApplication.instance() or QApplication([])

@pytest.fixture
def window(app,tmp_path):
    w=MainWindow(tmp_path);w.store.apply_batch([Course(1,'기업가정신'),Course(2,'비즈니스 일본어')],{(1,'assignment'):[]})
    w.store.add_timetable(1,0,'09:15','10:45','김 교수','A201',color='#7582E6')
    w.store.add_timetable(2,1,'11:00','12:30','이 교수','B301',color='#459CD4')
    w._sessions=w.store.timetable();w._reload();w.select_page(3);w.main_stack._settle();w.show();app.processEvents()
    yield w
    w.dispose();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()

def test_old_timetable_schema_gets_color_without_losing_rows(tmp_path):
    path=tmp_path/'old.db';db=sqlite3.connect(path)
    db.execute("CREATE TABLE timetable(id INTEGER PRIMARY KEY,course_id INTEGER,day INTEGER,start_time TEXT,end_time TEXT,professor TEXT,room TEXT)")
    db.execute("INSERT INTO timetable VALUES(1,1,0,'09:00','10:00','교수','A201')");db.commit();db.close()
    store=Store(path);row=store.timetable()[0]
    assert row['color']=='' and row['room']=='A201' and row['professor']=='교수'
    store.set_timetable_color(1,'#459cd4');store.close();again=Store(path)
    assert again.timetable()[0]['color']=='#459CD4';again.close()

def test_color_selection_and_drag_target_persist(window):
    item=window._sessions[0];window.timetable.select(item['id']);window.timetable.picker.choose('#CF779A')
    assert window.store.timetable()[0]['color']=='#CF779A'
    window.timetable.move_requested.emit(item['id'],2,'09:30','11:00')
    row=next(r for r in window.store.timetable() if r['id']==item['id'])
    assert (row['day'],row['start_time'],row['end_time'],row['color'])==(2,'09:30','11:00','#CF779A')

def test_conflicting_drag_keeps_saved_time_and_restores_card(window):
    item=window._sessions[0];window.timetable.move_requested.emit(item['id'],1,'11:30','13:00')
    row=next(r for r in window.store.timetable() if r['id']==item['id'])
    assert row['day']==0 and row['start_time']=='09:15'
    assert '겹치는' in window.status.full_text
    assert window.timetable.surface.blocks[item['id']].row['day']==0

def test_editor_retains_invalid_input_in_place(app):
    d=SessionEditor([Course(1,'과목')]);d.show();d.start.setTime(d.end.time());d._save()
    assert d.result()!=QDialog.DialogCode.Accepted and '종료' in d.error.text()
    d.start.setTime(d.start.time().addSecs(-3600));d.validation=lambda values:'같은 요일에 겹치는 수업이 있습니다.';d._save()
    assert d.isVisible() and '겹치는' in d.error.text()
    d.close();d.deleteLater();app.processEvents()

def test_slot_mapping_uses_quarter_hours(app):
    surface=WeekSurface();surface.resize(1052,900);surface.hour_height=80;surface.relayout()
    day,start=surface.slot_at(QPoint(52+2*200+10,12+100))
    assert day==2 and start==9*60+15
    surface.deleteLater();app.processEvents()

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

def test_calix_brand_credit_profile_and_native_controls(window,app):
    assert window.windowTitle()=='Calix' and not window.menuBar().isVisible()
    assert window.command_menu.menu() is not None
    window.credits();app.processEvents();d=window._dialogs['credits']
    assert d.windowTitle()=='Calix 크레딧' and d.avatar.property('profileLoaded') and not d.avatar.pixmap().isNull()
    assert asset_path('profile.png').is_file()
    d.close();app.processEvents()

def test_refresh_reuses_native_blocks(window,app):
    from PySide6.QtWidgets import QWidget
    before=len(window.timetable.findChildren(QWidget));ids={key:id(card) for key,card in window.timetable.surface.blocks.items()}
    for _ in range(30):window.timetable.set_data(window._sessions,{1:'기업가정신',2:'비즈니스 일본어'});app.processEvents()
    assert {key:id(card) for key,card in window.timetable.surface.blocks.items()}==ids
    assert len(window.timetable.findChildren(QWidget))==before

def test_metrics_filter_the_same_course_context(window):
    from datetime import timedelta
    now=datetime.now(KST)
    events=[Event('a',1,'기업가정신','assignment','하루 뒤',(now+timedelta(days=1)).isoformat(),False),
            Event('b',2,'일본어','movie','이틀 뒤',(now+timedelta(days=2)).isoformat(),False)]
    window.snapshot=__import__('learning_calendar.snapshot',fromlist=['Snapshot']).Snapshot(events,[Course(1,'기업가정신'),Course(2,'일본어')])
    window._reload_course_filter();window.select_page(0);window.course_select.setCurrentIndex(window.course_select.findData(1));window._metric_filter(7)
    assert window.metric_labels[1].text()=='1' and [e.key for e in window._filtered]==['a']
    assert window.metric_buttons[1].property('active')

def test_legacy_credentials_are_read_without_rewriting(monkeypatch):
    import keyring
    from learning_calendar.preferences import read_account,read_password
    values={('BUFS Learning Calendar','__account_id__'):'synthetic-id',('BUFS Learning Calendar/password','synthetic-id'):'synthetic-password'}
    monkeypatch.setattr(keyring,'get_password',lambda service,key:values.get((service,key)))
    monkeypatch.setattr(keyring,'set_password',lambda *args:pytest.fail('read must not rewrite secrets'))
    assert read_account()=='synthetic-id' and read_password('synthetic-id')=='synthetic-password'
