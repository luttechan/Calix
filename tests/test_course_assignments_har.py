"""Course assignments and submission shapes from the supplied 15:57 HAR."""
import json
from pathlib import Path
from dataclasses import replace
from types import SimpleNamespace
import pytest
import requests
from learning_calendar.models import Course,Event,deadline_display
from learning_calendar.parsers import parse_assignments
from learning_calendar.sync import CampusClient,AuthenticationRequired,sync_summary
from learning_calendar.storage import Store


def fixture():return json.loads((Path(__file__).parent/'fixtures/course_assignments_har.json').read_text())


def test_har_has_seven_assignments_six_submitted_and_one_unsubmitted():
    data=fixture();events=parse_assignments(Course(1,'Course'),data['groups'],data['submissions'])
    assert len(events)==7 and len({e.key for e in events})==7
    assert sum(e.completed for e in events)==6 and all(e.completion_verified for e in events)
    assert [e.key for e in events if not e.completed]==['assignment:1:107']


@pytest.mark.parametrize('primary',['forbidden','empty','bad_json'])
def test_course_page_routes_recover_when_flat_endpoint_fails(monkeypatch,primary):
    data=fixture();client=CampusClient([]);calls=[]
    def pages(path,*args,**kwargs):
        calls.append((path,client.session.headers['Referer']))
        if path.endswith('/assignment_groups'):return data['groups']
        if path.endswith('/students/submissions'):return data['submissions']
        if primary=='forbidden':raise requests.HTTPError('403')
        if primary=='bad_json':raise ValueError('unexpected JSON')
        return []
    monkeypatch.setattr(client,'_paginated',pages)
    events=client._course_assignments(Course(1,'Course'))
    assert len(events)==7 and sum(e.completed for e in events)==6
    assert len(calls)==3 and all(ref=='https://canvas.bufs.ac.kr/courses/1/assignments' for _,ref in calls)
    assert client.session.headers['Referer']=='https://canvas.bufs.ac.kr/'
    client.session.close()


def test_separate_submission_endpoint_supplies_missing_completion(monkeypatch):
    data=fixture();client=CampusClient([]);calls=[]
    def pages(path,*args,**kwargs):
        calls.append(path)
        return data['submissions'] if path.endswith('/students/submissions') else data['groups'][3]['assignments']
    monkeypatch.setattr(client,'_paginated',pages)
    events=client._course_assignments(Course(1,'Course'))
    assert sum(e.completed for e in events)==6 and len(calls)==2
    client.session.close()


def test_fully_detailed_flat_endpoint_keeps_single_request(monkeypatch):
    data=fixture();assignments=data['groups'][3]['assignments']
    for a,s in zip(assignments,data['submissions']):a['submission']=s
    client=CampusClient([]);calls=[]
    def pages(path,*args,**kwargs):calls.append(path);return assignments
    monkeypatch.setattr(client,'_paginated',pages)
    events=client._course_assignments(Course(1,'Course'))
    assert len(events)==7 and sum(e.completed for e in events)==6 and len(calls)==1
    client.session.close()


def test_expired_session_does_not_try_other_endpoints(monkeypatch):
    client=CampusClient([]);calls=[]
    def pages(path,*args,**kwargs):calls.append(path);raise AuthenticationRequired('expired')
    monkeypatch.setattr(client,'_paginated',pages)
    with pytest.raises(AuthenticationRequired):client._course_assignments(Course(1,'Course'))
    assert len(calls)==1
    client.session.close()


def test_failed_submission_request_keeps_previous_assignment_batch(monkeypatch,tmp_path):
    data=fixture();course=Course(1,'Course');client=CampusClient([])
    def pages(path,*args,**kwargs):
        if path.endswith('/modules'):return []
        if path.endswith('/assignments'):return data['groups'][3]['assignments']
        raise requests.ConnectionError('synthetic outage')
    monkeypatch.setattr(client,'_paginated',pages)
    batches,notes=client._fetch_course(course,lambda *_:None)
    assert (1,'assignment') not in batches and client.course_checks[1]['assignment_state']=='failed'
    store=Store(tmp_path/'test.db');old=Event('assignment:1:107',1,'Course','assignment','Previous',None,True)
    store.apply_batch([course],{(1,'assignment'):[old]});store.set_note(old.key,'Keep note')
    store.apply_batch([course],batches)
    assert store.events()[0].completed and store.events()[0].note=='Keep note'
    assert sync_summary(notes,client.course_checks)=='조회 실패 1건'
    store.close();client.session.close()


def test_unknown_submission_is_not_mislabeled_as_overdue_or_reset(tmp_path):
    data=fixture();data['submissions']=data['submissions'][:-1]
    events=parse_assignments(Course(1,'Course'),data['groups'],data['submissions'])
    unknown=events[-1]
    assert not unknown.completion_verified and deadline_display(unknown)==('제출 상태 미확인','neutral')
    store=Store(tmp_path/'test.db');store.apply_batch([Course(1,'Course')],{(1,'assignment'):[replace(unknown,completed=True,completion_verified=True)]})
    store.apply_batch([Course(1,'Course')],{(1,'assignment'):events})
    row=next(e for e in store.events() if e.key==unknown.key)
    assert row.completed and not row.completion_verified
    store.close()


@pytest.mark.parametrize('checks,expected',[
    ({1:{'video_state':'unverified','assignment_state':'complete'}},'시청 상태 미확인'),
    ({1:{'video_state':'complete','assignment_state':'unverified'}},'제출 상태 미확인'),
    ({1:{'video_state':'authentication','assignment_state':'complete'}},'영상 인증 필요'),
    ({1:{'video_state':'failed','assignment_state':'failed'}},'조회 실패 2건'),
])
def test_sync_status_distinguishes_failures_from_unverified_states(checks,expected):
    assert sync_summary(['notice'],checks)==expected
    assert sync_summary([],checks)==''


def test_worker_persists_the_specific_sync_status(monkeypatch,tmp_path):
    from learning_calendar.worker import SyncTask
    data=fixture();course=Course(1,'Course');events=parse_assignments(course,data['groups'],data['submissions'])
    task=SyncTask([],tmp_path/'test.db');results=[]
    monkeypatch.setattr(task,'_fetch_network',lambda:('1',[course],{(1,'assignment'):events},['state unknown'],False,{1:{'video_state':'unverified','assignment_state':'complete'}}))
    task.success.connect(results.append);task.run()
    assert len(results)==1 and results[0]['sync_summary']=='시청 상태 미확인'
    store=Store(tmp_path/'test.db')
    assert store.get_meta('sync_partial')=='1' and store.get_meta('sync_summary')=='시청 상태 미확인'
    assert len(store.events())==7 and sum(e.completed for e in store.events())==6
    store.close()
