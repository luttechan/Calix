from dataclasses import replace
import sqlite3
from learning_calendar.models import Course,deadline_display
from learning_calendar.parsers import parse_movies
from learning_calendar.storage import Store,SCHEMA
from learning_calendar.sync import CampusClient

def modules():
    return [{'title':'영상자료','module_items':[
        {'completed':True,'content_data':{'item_id':1,'title':'시청 영상','item_content_data':{'content_type':'movie'}}},
        {'content_data':{'item_id':2,'title':'상태 없는 영상','item_content_data':{'content_type':'movie'}}},
        {'completed':False,'content_data':{'item_id':3,'title':'상세 정보 없는 영상','item_content_type':'movie'}},
        {'completed':True,'content_data':{'item_id':4,'item_content_data':{'content_type':'doc'}}},
        {'published':False,'content_data':{'item_id':5,'item_content_type':'movie'}}]}]

def test_missing_one_completion_does_not_remove_course_videos():
    rows=parse_movies(Course(1,'삶과 철학'),modules())
    assert len(rows)==3 and [e.key for e in rows]==['movie:1:1','movie:1:2','movie:1:3']
    assert rows[0].completed and rows[0].completion_verified
    assert not rows[1].completed and not rows[1].completion_verified
    assert rows[2].completion_verified and not rows[2].completed
    assert deadline_display(rows[1])==('시청 상태 미확인','neutral')

def test_unknown_completion_keeps_known_state_and_notes_across_sync(tmp_path):
    path=tmp_path/'learning.db';store=Store(path);course=Course(1,'삶과 철학');events=parse_movies(course,modules())
    store.apply_batch([course],{(1,'movie'):[replace(e,completed=True,completion_verified=True) for e in events]})
    store.set_note(events[1].key,'메모 유지')
    store.apply_batch([course],{(1,'movie'):events});store.close();store=Store(path)
    rows={e.key:e for e in store.events()}
    assert len(rows)==3 and rows[events[1].key].completed
    assert not rows[events[1].key].completion_verified and rows[events[1].key].note=='메모 유지'
    assert not rows[events[2].key].completed
    store.apply_batch([course],{(1,'movie'):[replace(e,completion_verified=True) for e in events]})
    assert all(e.completion_verified for e in store.events())
    store.close()

def test_old_database_migrates_without_changing_completion(tmp_path):
    path=tmp_path/'learning.db';db=sqlite3.connect(path);db.executescript(SCHEMA)
    db.execute("INSERT INTO events(key,course_id,kind,title,due_at,completed,updated_at) VALUES('video',1,'movie','기존 영상',NULL,1,'')");db.commit();db.close()
    store=Store(path);row=store.events()[0];assert row.completed and row.completion_verified;store.close()

def test_sync_keeps_partial_state_video_list_and_reports_it(monkeypatch):
    client=CampusClient([])
    monkeypatch.setattr(client,'_paginated',lambda path,*args,**kwargs:modules() if path.endswith('/modules') else [])
    batches,notes=client._fetch_course(Course(1,'삶과 철학'),lambda *_:None)
    assert len(batches[(1,'movie')])==3 and len(notes)==1 and '시청 상태 미확인' in notes[0]
    assert client.course_checks[1]['videos']==3 and client.course_checks[1]['unknown']==1 and not client.course_checks[1]['videos_verified']
    assert not client.movie_auth_required
    client.session.close()
