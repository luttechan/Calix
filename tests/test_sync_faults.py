import io
import sqlite3
from types import SimpleNamespace
from dataclasses import replace
import pytest
import requests
from learning_calendar.models import Course,Event
from learning_calendar.parsers import parse_movies,parse_assignments
from learning_calendar.sync import CampusClient,AuthenticationRequired,SyncCancelled
from learning_calendar.storage import Store
from learning_calendar.worker import SyncTask


def movie(identifier,**extra):
    return dict(content_data=dict(item_id=identifier,title='Video',item_content_data={'content_type':'movie'}),completed=True,**extra)


@pytest.mark.parametrize('bad',[None,{}, {'content_data':{'item_content_type':'commons'}},
                                {'content_data':{'item_id':{},'item_content_type':'movie'}},
                                {'content_data':{'item_id':2,'item_content_type':'movie','due_at':[]}}])
def test_malformed_video_does_not_discard_good_items_or_archive_previous(bad,tmp_path):
    rows=parse_movies(Course(1,'Course'),[{'module_items':[movie(1),bad]}])
    assert len(rows)==1 and not rows.complete
    store=Store(tmp_path/'db');old=Event('movie:1:2',1,'Course','movie','Saved',None,True)
    store.apply_batch([Course(1,'Course')],{(1,'movie'):[old]});store.set_note(old.key,'Keep')
    stats=store.apply_batch([Course(1,'Course')],{(1,'movie'):rows})
    saved={e.key:e for e in store.events()}
    assert len(saved)==2 and saved[old.key].note=='Keep' and stats['archived']==0
    store.close()


def test_conflicting_duplicate_id_keeps_existing_record(tmp_path):
    a=movie(1);b=movie(1);b['completed']=False
    rows=parse_movies(Course(1,'Course'),[{'module_items':[a,b,movie(2)]}])
    assert [e.key for e in rows]==['movie:1:2'] and not rows.complete


@pytest.mark.parametrize('bad',[None,{'id':2,'submission_types':42},{'id':{},'name':'Broken'},
                                {'id':2,'due_at':{'bad':'date'}}])
def test_malformed_assignment_is_isolated(bad):
    good={'id':1,'name':'Good','submission':{'workflow_state':'submitted'}}
    rows=parse_assignments(Course(1,'Course'),[{'assignments':[good,bad]}],[])
    assert len(rows)==1 and rows[0].completed and not rows.complete


def test_malformed_submission_state_does_not_break_course(monkeypatch):
    client=CampusClient([])
    def pages(path,*args,**kwargs):
        if path.endswith('/assignments'):return [{'id':1,'submission':{'workflow_state':[]}}]
        return [{'assignment_id':1,'workflow_state':'submitted'}]
    monkeypatch.setattr(client,'_paginated',pages)
    rows=client._course_assignments(Course(1,'Course'))
    assert len(rows)==1 and rows[0].completed and rows[0].completion_verified
    client.session.close()


@pytest.mark.parametrize('status',[429,500,502,503,504])
def test_transient_get_retries_are_bounded(monkeypatch,status):
    client=CampusClient([]);calls=[];closed=[]
    def get(*args,**kwargs):
        calls.append(True)
        return SimpleNamespace(status_code=status,close=lambda:closed.append(True))
    monkeypatch.setattr(client.session,'get',get);monkeypatch.setattr(client.cancel_event,'wait',lambda *_:False)
    response=client._request_get('https://canvas.bufs.ac.kr/api/v1/courses')
    assert response.status_code==status and len(calls)==3 and len(closed)==2
    client.session.close()


@pytest.mark.parametrize('error',[requests.Timeout,requests.ConnectionError])
def test_transient_connection_failure_can_recover(monkeypatch,error):
    client=CampusClient([]);calls=[]
    def get(*args,**kwargs):
        calls.append(True)
        if len(calls)==1:raise error('temporary')
        return SimpleNamespace(status_code=200)
    monkeypatch.setattr(client.session,'get',get);monkeypatch.setattr(client.cancel_event,'wait',lambda *_:False)
    assert client._request_get('https://canvas.bufs.ac.kr/').status_code==200 and len(calls)==2
    client.session.close()


def test_certificate_error_is_not_retried(monkeypatch):
    client=CampusClient([]);calls=[]
    def get(*args,**kwargs):calls.append(True);raise requests.exceptions.SSLError('certificate')
    monkeypatch.setattr(client.session,'get',get)
    with pytest.raises(requests.exceptions.SSLError):client._request_get('https://canvas.bufs.ac.kr/')
    assert len(calls)==1;client.session.close()


def test_cancellation_interrupts_backoff(monkeypatch):
    client=CampusClient([]);calls=[]
    def get(*args,**kwargs):calls.append(True);return SimpleNamespace(status_code=503,close=lambda:None)
    monkeypatch.setattr(client.session,'get',get)
    monkeypatch.setattr(client.cancel_event,'wait',lambda *_:client.cancel_event.set())
    with pytest.raises(SyncCancelled):client._request_get('https://canvas.bufs.ac.kr/')
    assert len(calls)==1;client.session.close()


def test_stream_size_limit_closes_connection():
    client=CampusClient([]);response=requests.Response();response.raw=io.BytesIO(b'x'*64)
    with pytest.raises(ValueError):client._read_response(response,32)
    assert response.raw.closed;client.session.close()


def test_html_error_page_does_not_mean_expired_login(monkeypatch):
    client=CampusClient([])
    response=SimpleNamespace(status_code=200,headers={'content-type':'text/html'},raise_for_status=lambda:None)
    monkeypatch.setattr(client.session,'get',lambda *a,**k:response)
    with pytest.raises(ValueError):client._get('/api/v1/courses')
    client.session.close()


@pytest.mark.parametrize('failure',['disk','cancel'])
def test_sync_transaction_rolls_back_events_and_metadata(monkeypatch,tmp_path,failure):
    path=tmp_path/'db';course=Course(1,'Course');old=Event('assignment:1:1',1,'Course','assignment','Previous',None,True)
    store=Store(path);store.apply_batch([course],{(1,'assignment'):[old]});store.set_meta('last_sync','previous');store.set_note(old.key,'Keep note');store.close()
    task=SyncTask([],path);results=[];errors=[];task.success.connect(results.append);task.error.connect(errors.append)
    fresh=replace(old,title='New title',completed=False)
    monkeypatch.setattr(task,'_fetch_network',lambda:('1',[course],{(1,'assignment'):[fresh]},[],False,{}))
    original=Store.set_meta
    def set_meta(self,key,value,**kwargs):
        if key=='sync_summary':
            if failure=='disk':raise sqlite3.OperationalError('disk full')
            task.cancel()
        return original(self,key,value,**kwargs)
    monkeypatch.setattr(Store,'set_meta',set_meta);task.run()
    assert not results and bool(errors)==(failure=='disk')
    store=Store(path);row=store.events()[0]
    assert row.title=='Previous' and row.completed and row.note=='Keep note'
    assert store.get_meta('last_sync')=='previous' and not store.get_meta('canvas_user_id')
    store.close()


def test_dead_network_worker_does_not_wait_forever(monkeypatch):
    import learning_calendar.worker as worker
    class DeadThread:
        def __init__(self,*args,**kwargs):pass
        def start(self):pass
        def is_alive(self):return False
    monkeypatch.setattr(worker.threading,'Thread',DeadThread)
    with pytest.raises(RuntimeError,match='중단'):SyncTask([],':memory:')._fetch_network()


