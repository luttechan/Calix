import copy
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
import pytest
from learning_calendar.dom_videos import parse_screen,screen_date
from learning_calendar.models import Course
from learning_calendar.storage import Store


def snapshot():
    return dict(state='ready',course_id='1',owner='1',term='2026년 2학기',weeks=15,expected=15,items=[dict(
        kind='mp4',title='Video',url='/courses/1/modules/items/101',week='1주차',completed=True,
        start='8월 30일 오전 00:00',due='9월 16일 오후 11:59',lock='12월 9일 오후 11:59')])


@pytest.mark.parametrize('value,hour', [('9월 1일 오전 00:00',0),('9월 1일 오전 12:00',0),('9월 1일 오후 12:00',12),('9월 1일 오후 01:00',13),('2027년 9월 1일 23:00',23)])
def test_screen_dates(value,hour):
    from datetime import datetime
    date=datetime.fromisoformat(screen_date(value,2026))
    assert date.hour==hour and date.utcoffset().total_seconds()==32400
    assert date.year==(2027 if value.startswith('2027') else 2026)


@pytest.mark.parametrize('value',['tomorrow','2월 30일 오후 1:00','1월 1일 오후 13:00',{},'1월 1일 23:99'])
def test_invalid_date_is_not_guessed(value):
    with pytest.raises((ValueError,TypeError)):screen_date(value,2026)


def test_rendered_periods_and_completion():
    events=parse_screen(Course(1,'Course'),snapshot());e=events[0]
    assert events.complete and e.key=='movie:1:101' and e.completed and e.completion_verified
    assert e.start_at=='2026-08-30T00:00:00+09:00'
    assert e.due_at=='2026-09-16T23:59:00+09:00'
    assert e.lock_at=='2026-12-09T23:59:00+09:00' and e.week=='1주차'


@pytest.mark.parametrize('field,value',[('state','loading'),('course_id',2),('term',''),('weeks',True),('weeks',0),('weeks','15'),('expected',16),('items',{})])
def test_incomplete_screen_does_not_authorize_archival(field,value):
    data=snapshot();data[field]=value
    with pytest.raises(ValueError):parse_screen(Course(1,'Course'),data)


@pytest.mark.parametrize('url',['https://example.org/courses/1/modules/items/101','https://canvas.bufs.ac.kr:444/courses/1/modules/items/101','/courses/2/modules/items/101','/courses/1/modules/items/no-id'])
def test_untrusted_or_other_course_link_is_rejected(url):
    data=snapshot();data['items'][0]['url']=url
    events=parse_screen(Course(1,'Course'),data)
    assert not events and not events.complete


def test_conflicting_duplicate_never_overwrites_existing_data():
    data=snapshot();data['items'].append({**data['items'][0],'completed':False})
    data['items'].append(copy.deepcopy(data['items'][0]))
    events=parse_screen(Course(1,'Course'),data)
    assert not events and not events.complete


def test_unknown_completion_preserves_previous_completed_state_and_metadata():
    data=snapshot();course=Course(1,'Course');events=parse_screen(course,data)
    store=Store(':memory:')
    try:
        legacy=replace(events[0],key='movie:1:legacy-api-id')
        store.apply_batch([course],{(1,'movie'):[legacy]});store.set_note(legacy.key,'Keep')
        data['items'][0].update(completed=None,attendance='',title='New source name')
        rows=parse_screen(course,data);assert not rows[0].completion_verified
        store.apply_batch([course],{(1,'movie'):rows});stored=store.events()
        assert len(stored)==1 and stored[0].key==legacy.key and stored[0].note=='Keep'
        assert stored[0].completed and stored[0].start_at==events[0].start_at and stored[0].lock_at==events[0].lock_at
    finally:store.close()


def test_rendered_fixture_in_real_chromium():
    # A separate interpreter initializes WebEngine before QApplication.
    script=r'''
import os,sys,json,time
sys.path[:0]=json.loads(os.environ['CALIX_TEST_PATHS'])
from pathlib import Path
from PySide6.QtCore import Qt,QUrl,QCoreApplication,QEvent
QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineCore import QWebEngineProfile,QWebEnginePage
from learning_calendar.dom_videos import SNAPSHOT_SCRIPT,parse_screen
from learning_calendar.models import Course
app=QApplication([]);profile=QWebEngineProfile();page=QWebEnginePage(profile);result=[]
page.setHtml(Path('tests/fixtures/learningx_rendered.html').read_text(encoding='utf-8'),QUrl('https://canvas.bufs.ac.kr/courses/1/external_tools/1'))
def collect(value):
    if not isinstance(value,str):return
    try:decoded=json.loads(value)
    except ValueError:return
    if decoded.get('state')=='ready':result.append(decoded)
limit=time.monotonic()+12
while not result and time.monotonic()<limit:
    app.processEvents();time.sleep(.02);page.runJavaScript(SNAPSHOT_SCRIPT,collect)
assert result,'Rendered DOM was not ready'
rows=parse_screen(Course(1,'Course'),result[0])
assert rows.complete and len(rows)==17 and sum(e.completed for e in rows)==11
assert result[0]['weeks']==15
assert not any(key in result[0] for key in ('user_name','user_login','user_email'))
page.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
profile.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
print('RENDERED_DOM_OK')
'''
    env=os.environ.copy();env['CALIX_TEST_PATHS']=json.dumps(sys.path)
    completed=subprocess.run([sys.executable,'-B','-c',script],env=env,capture_output=True,text=True,timeout=25)
    assert completed.returncode==0,completed.stderr[-2500:]
    assert 'RENDERED_DOM_OK' in completed.stdout
