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

@pytest.mark.parametrize('point',[QPoint(-1900,0),QPoint(-1,1060),QPoint(-1900,1060),QPoint(-1,0)])
def test_popup_stays_inside_negative_monitor(point):
    from learning_calendar.event_popover import popup_position
    area=QRect(-1920,0,1920,1080);size=QSize(430,610);position=popup_position(point,size,area)
    assert area.contains(QRect(position,size))

def test_calendar_chip_click_filters_custom_and_builtin_types(app):
    from learning_calendar.calendar_view import DayBadges
    event=imported();movie=replace(event,key='movie:1:2',kind='movie');custom=replace(event,key='assignment:1:3',type_id=4,type_name='발표',type_color='#7582E6')
    badge=DayBadges();badge.resize(300,24);badge.set_events(event.due.date(),[event,movie,custom]);badge.configure(1,1,300,22,[('발표',1,'#7582E6')]);badge.show();app.processEvents()
    calls=[];badge.details_requested.connect(lambda *args:calls.append(args))
    for label,key in ((badge.assignment,event.key),(badge.movie,movie.key),(badge.custom[0],custom.key)):
        QTest.mouseClick(label,Qt.MouseButton.LeftButton);assert [row.key for row in calls[-1][1]]==[key]
    badge.close();badge.deleteLater()

def test_popup_saves_on_close_and_timetable_counts_exclude_past_completed(app,tmp_path):
    from learning_calendar.gui import MainWindow
    w=MainWindow(tmp_path);event=imported();now=datetime.now(KST)
    w.store.apply_batch([Course(1,'과목')],{(1,'assignment'):[event,replace(event,key='assignment:1:100',due_at=(now-timedelta(days=1)).isoformat()),replace(event,key='assignment:1:101',completed=True)],(1,'movie'):[replace(event,key='movie:1:22',kind='movie')]})
    w.store.add_timetable(1,0,'09:00','10:30','홍길동','A201');w._sessions=w.store.timetable();w._reload();w.show();app.processEvents()
    w.open_event(w.snapshot.by_key[event.key]);popup=w._event_popover
    popup.title.setText('편집한 이름');popup.title.textEdited.emit('편집한 이름');popup.note.setPlainText('보존 메모');assert popup.close()
    assert w.store.events()[0].note or any(e.note=='보존 메모' for e in w.store.events())
    assert w.snapshot.by_key[event.key].title=='편집한 이름'
    w.select_page(3);w.main_stack._settle();app.processEvents();view=w.timetable
    assert view.remaining_assignments.text()=='남은 과제 1건' and view.remaining_videos.text()=='남은 영상 1건'
    card=next(iter(view.surface.blocks.values()));assert card.room.full=='홍길동 / A201' and card.assignments.text()=='과제 1'
    assert view.detail_prof.text()=='홍길동' and card.height()<120
    w.dispose();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()

def test_moving_background_is_opaque_deterministic_and_reuses_cache(app):
    from learning_calendar.glass import GlassBackdrop
    from learning_calendar.design import apply_palette
    app.setProperty('calixGlass',True);apply_palette(app,'mint');w=GlassBackdrop();w.resize(500,400);w.show();app.processEvents();first=w.grab().toImage();count=w.render_count
    for offset in range(4):w.move(40+offset*5,50);w.repair_after_move();w.repaint(0,0,50,50);app.processEvents()
    assert first==w.grab().toImage() and w.render_count==count
    assert all(w._field.pixelColor(x,y).alpha()==255 for x,y in ((0,0),(320,210),(639,419)))
    w.close();w.deleteLater()

def test_popup_autosave_switch_and_repeated_close_release_widgets(app,tmp_path):
    from learning_calendar.gui import MainWindow
    from learning_calendar.event_popover import EventPopover
    w=MainWindow(tmp_path);event=imported();other=replace(event,key='assignment:1:2',title='두 번째 일정')
    w.store.apply_batch([Course(1,'과목')],{(1,'assignment'):[event,other]});w._reload()
    w.show_calendar_details(event.due.date(),w.snapshot.events,QPoint(100,100));popup=w._event_popover;second_key=popup.rows[1].key
    popup.title.setText('자동 저장');popup.title.textEdited.emit('자동 저장');QTest.qWait(750)
    assert w.store.events()[0].title=='자동 저장'
    popup.list.setCurrentIndex(popup.list.model().index(1));popup.note.setPlainText('두 번째 메모');assert popup.close()
    assert w.snapshot.by_key[second_key].note=='두 번째 메모'
    for _ in range(8):
        w.open_event(w.snapshot.by_key[event.key]);w._event_popover.close();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    assert not w.findChildren(EventPopover) and w._event_popover is None
    w.dispose();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
