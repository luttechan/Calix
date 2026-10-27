from learning_calendar.models import Course, Event, parse_datetime
from learning_calendar.parsers import course_list,parse_movies,parse_assignments,safe_url
from learning_calendar.storage import Store
from datetime import datetime,timezone


def test_course_list():
    out=course_list([{'id':1,'longName':'Japanese'},{'id':'2','shortName':'English'}])
    assert [c.id for c in out]==[1,2]


def test_movie_only_video():
    course=Course(42,'Example')
    payload=[{'title':'1주차','module_items':[
      {'title':'A','content_id':100,'content_data':{'item_id':100,'title':'Movie','due_at':'2026-10-18T14:59:59Z','item_content_data':{'content_type':'movie'}},'completed':True,'url':'/some-path'},
      {'title':'Assignment','content_id':200,'content_type':'assignment','content_data':{'item_id':200}},
      {'title':'Not a video','content_id':300,'content_data':{'item_id':300,'item_content_data':{'content_type':'doc'}}},
    ]}]
    result=parse_movies(course,payload)
    assert len(result)==1
    assert result[0].completed
    assert result[0].key=='movie:42:100'
    assert result[0].due.strftime('%H:%M')=='23:59'


def test_assignments_filters_quizzes():
    course=Course(10,'Example')
    groups=[{'name':'과제', 'assignments':[
       {'id':2,'name':'Essay','due_at':'2026-10-20T14:59:59Z','published':True,'is_quiz_assignment':False,'submission_types':['online_text_entry']},
       {'id':3,'name':'Quiz','is_quiz_assignment':True,'submission_types':['online_quiz']},
       {'id':4,'name':'Test','is_quiz_assignment':False,'submission_types':['online_quiz']},
       {'id':5,'name':'Hidden','published':False}
    ]}]
    sub=[{'assignment_id':2,'workflow_state':'submitted','submitted_at':'2026-10-10T01:01:00Z'}]
    result=parse_assignments(course,groups,sub)
    assert len(result)==1 and result[0].completed
    assert result[0].title=='Essay'


def test_no_malicious_url():
    assert safe_url('https://phish.example/evil')==''
    assert safe_url('javascript:alert(1)')==''


def test_store_preserves_note_and_marks_removed(tmp_path):
    store=Store(tmp_path/'cache.sqlite3')
    c=Course(11,'Sample')
    a=Event(key='movie:11:11',course_id=11,course_name=c.name,kind='movie',title='Video',due_at='2026-10-14T01:00:00Z',completed=False)
    summary=store.apply_batch([c],{(11,'movie'):[a]})
    assert summary['new']==1
    store.set_note(a.key,'my important note')
    store.set_starred(a.key,True)
    a.due_at='2026-10-15T01:00:00Z'
    summary=store.apply_batch([c],{(11,'movie'):[a]})
    assert summary['updated']==1
    assert store.events()[0].note=='my important note'
    assert store.events()[0].starred
    store.apply_batch([c],{(11,'movie'):[]})
    assert not store.events() and len(store.events(True))==1
    store.close()


def test_failed_course_kind_never_pruned(tmp_path):
    store=Store(tmp_path/'a.db')
    c=Course(9,'Test')
    x=Event(key='assignment:9:1',course_id=9,course_name=c.name,kind='assignment',title='Homework',due_at=None,completed=False)
    store.apply_batch([c],{(9,'assignment'):[x]})
    store.apply_batch([c],{(9,'movie'):[]})
    assert store.events()[0].key==x.key
    store.close()
