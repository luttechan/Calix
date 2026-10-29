from dataclasses import replace
from datetime import datetime,timedelta,date
import hashlib
import json
from types import SimpleNamespace
import pytest
from PySide6.QtCore import Qt,QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from learning_calendar.models import Event,Course,KST,deadline_display
from learning_calendar.calendar_view import DayBadges,MonthCanvas
from learning_calendar.sync import CampusClient
from learning_calendar.storage import Store
from learning_calendar.updates import parse_release,version_key,trusted_download

@pytest.fixture(scope='module')
def app():return QApplication.instance() or QApplication([])

def dispose(widget,app):
    widget.close();widget.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()

def test_watched_and_unwatched_video_badges_are_separate_and_clickable(app):
    row=Event('movie:1:1',1,'과목','movie','영상','2026-11-02T23:59:00+09:00',False)
    done=replace(row,key='movie:1:2',completed=True)
    badge=DayBadges();badge.set_events(date(2026,11,2),[row,done]);badge.configure(0,1,300,22,movie_done=1)
    assert badge.movie.property('calendarOpacity')==1 and badge.movie_done.property('calendarOpacity')==.38
    assert badge.matching(badge.movie)==[row] and badge.matching(badge.movie_done)==[done]
    assert badge.movie_done.graphicsEffect() is None
    custom=replace(done,type_id=2,type_name='복습',type_color='#7582E6')
    badge.set_events(date(2026,11,2),[custom]);badge.configure(0,0,300,22,[('복습',1,'#7582E6',True)])
    assert badge.custom[0].property('completed') and badge.matching(badge.custom[0])==[custom]
    dispose(badge,app)

def test_sync_completion_reaches_actual_calendar_cell(app,tmp_path):
    from learning_calendar.gui import MainWindow
    row=Event('movie:1:1',1,'과목','movie','영상','2026-11-02T23:59:00+09:00',False)
    w=MainWindow(tmp_path);w.store.apply_batch([Course(1,'과목')],{(1,'movie'):[row]});w._reload()
    w.select_page(0);w.select_day(date(2026,11,2));w.show();app.processEvents();w.calendar._layout_badges()
    badge=next(b for b in w.calendar.badges if b.day==date(2026,11,2))
    assert not badge.movie.isHidden() and badge.movie_done.isHidden()
    w.store.apply_batch([Course(1,'과목')],{(1,'movie'):[replace(row,completed=True)]});w._reload();app.processEvents();w.calendar._layout_badges()
    assert badge.movie.isHidden() and not badge.movie_done.isHidden() and badge.movie_done.property('calendarOpacity')==.38
    w.dispose();dispose(w,app)

def test_overdue_assignment_is_red_in_list_and_table(app):
    from learning_calendar.event_table import ScheduleModel
    from learning_calendar.event_view import EventListModel
    now=datetime(2000,10,29,12,tzinfo=KST);row=Event('a',1,'과목','assignment','과제',(now-timedelta(seconds=1)).isoformat(),False)
    assert deadline_display(row,now)==('미완료','red')
    assert deadline_display(replace(row,completed=True),now)==('완료','done')
    model=ScheduleModel();model.set_events([row],now)
    assert model.index(0,4).data()=='미완료' and model.index(0,4).data(Qt.ItemDataRole.ForegroundRole).name()=='#d94b61'
    model=EventListModel();model.set_events([row]);assert '미완료' in model.index(0).data()

def test_overdue_calendar_badge_separates_submitted_and_pending(app):
    now=datetime.now(KST)
    late=Event('late',1,'과목','assignment','지난 과제',(now-timedelta(minutes=1)).isoformat(),False)
    pending=replace(late,key='pending',due_at=(now+timedelta(days=1)).isoformat())
    done=replace(late,key='done',completed=True)
    badge=DayBadges();badge.set_events(now.date(),[late,pending,done]);badge.configure(1,0,400,22,assignment_overdue=1,assignment_done=1)
    assert badge.assignment_overdue.text()=='미완료 1' and not badge.assignment_overdue.isHidden()
    assert '#d94b61' in badge.assignment_overdue.styleSheet().lower()
    assert badge.matching(badge.assignment_overdue)==[late] and badge.matching(badge.assignment)==[pending]
    assert badge.matching(badge.assignment_done)==[done] and badge.assignment_done.property('calendarOpacity')==.38
    badge.configure(0,0,400,22);assert badge.assignment_overdue.isHidden()
    dispose(badge,app)

def response(body,next_url=None):return SimpleNamespace(json=lambda:body,links={'next':{'url':next_url}} if next_url else {})

def test_full_course_api_follows_next_page_without_using_dashboard(monkeypatch):
    client=CampusClient([]);seen=[]
    def get(path,params):
        seen.append((path,params))
        if len(seen)==1:return response([{'id':1,'name':'첫 과목'}],'?page=2')
        return response([{'id':2,'name':'대시보드에 없는 과목'},{'id':1,'name':'첫 과목'}])
    monkeypatch.setattr(client,'_get',get)
    rows=client._list_courses()
    assert [r.id for r in rows]==[1,2] and rows[1].name=='대시보드에 없는 과목'
    assert seen[0][0]=='/api/v1/courses' and seen[0][1]['per_page']==100
    assert seen[1][0]=='https://canvas.bufs.ac.kr/api/v1/courses?page=2'
    client.session.close()

def test_modules_and_assignments_retrieve_all_pages_and_submission_state(monkeypatch):
    client=CampusClient([]);seen=[]
    def get(path,params):
        seen.append(path)
        if '/modules' in path:
            mid=2 if 'page=2' in path else 1
            return response({'modules':[{'module_id':mid,'module_items':[{'completed':mid==2,'content_data':{'item_id':mid,'title':str(mid),'item_content_data':{'content_type':'movie'}}}]}]},None if mid==2 else '?page=2')
        aid=2 if 'page=2' in path else 1
        return response([{'id':aid,'name':str(aid),'submission':{'workflow_state':'submitted' if aid==2 else 'unsubmitted'}}],None if aid==2 else '?page=2')
    monkeypatch.setattr(client,'_get',get)
    batches,notes=client._fetch_course(Course(1,'과목'),lambda *_:None)
    assert not notes and len(batches[(1,'movie')])==len(batches[(1,'assignment')])==2
    assert [e.completed for e in batches[(1,'movie')]]==[False,True]
    assert [e.completed for e in batches[(1,'assignment')]]==[False,True]
    assert len(seen)==4;client.session.close()

@pytest.mark.parametrize('link',['https://evil.invalid/api/v1/courses','https://canvas.bufs.ac.kr:444/api/v1/courses','https://user@canvas.bufs.ac.kr/api/v1/courses','/api/v1/users'])
def test_pagination_rejects_untrusted_next_before_request(monkeypatch,link):
    client=CampusClient([]);seen=[]
    def get(*args):seen.append(args);return response([],link)
    monkeypatch.setattr(client,'_get',get)
    with pytest.raises(RuntimeError):client._list_courses()
    assert len(seen)==1;client.session.close()

def test_failed_second_page_keeps_previous_video_batch(app,tmp_path,monkeypatch):
    import requests
    store=Store(tmp_path/'learning.db');course=Course(1,'과목');row=Event('movie:1:99',1,'과목','movie','기존',None,False)
    store.apply_batch([course],{(1,'movie'):[row]});client=CampusClient([])
    def get(path,params):
        if '/modules' in path:
            if 'page=2' in path:raise requests.ConnectionError('offline')
            return response([], '?page=2')
        return response([])
    monkeypatch.setattr(client,'_get',get);batches,notes=client._fetch_course(course,lambda *_:None)
    assert (1,'movie') not in batches and notes
    store.apply_batch([course],batches);assert store.events()[0].key==row.key
    store.close();client.session.close()

def release_payload(blob=b'installer'):
    from learning_calendar.updates import RELEASES
    tag='v99.0.0';name='Calix-99.0.0-Setup-x64.exe'
    return dict(tag_name=tag,html_url=f'{RELEASES}/tag/{tag}',assets=[dict(name=name,browser_download_url=f'{RELEASES}/download/{tag}/{name}',digest='sha256:'+hashlib.sha256(blob).hexdigest(),size=len(blob))])

def test_release_version_and_official_installer_validation():
    assert version_key('v1.0.10')>version_key('1.0.9')>version_key('v1.0.8-r3')
    payload=release_payload();release=parse_release(payload)
    assert release.digest==hashlib.sha256(b'installer').hexdigest() and release.size==9
    for change in ({'digest':None},{'size':-1},{'browser_download_url':'https://evil.invalid/install.exe'}):
        bad=release_payload();bad['assets'][0].update(change)
        with pytest.raises(ValueError):parse_release(bad)
    for tag in ('v1.0.10-beta','../setup','1.0.10/evil'):
        with pytest.raises(ValueError):version_key(tag)
    assert not trusted_download('https://github.com/evil/download.exe')
    assert not trusted_download('https://release-assets.githubusercontent.com:444/a')

def test_home_cache_expires_at_deadline_and_reuses_same_minute(app,monkeypatch):
    from learning_calendar.home_view import HomeView
    from learning_calendar.snapshot import Snapshot
    now=datetime(2026,10,29,12,tzinfo=KST)
    row=Event('a',1,'과목','assignment','과제',(now+timedelta(seconds=20)).isoformat(),False)
    snapshot=Snapshot([row]);calls=[];pending=snapshot.pending
    monkeypatch.setattr(snapshot,'pending',lambda time:(calls.append(time),pending(time))[1])
    view=HomeView();view.update_snapshot(snapshot,now);view.update_snapshot(snapshot,now+timedelta(seconds=10))
    assert len(calls)==1 and view.remaining_card.target==1
    view.update_snapshot(snapshot,now+timedelta(seconds=20));assert len(calls)==2 and view.remaining_card.target==0
    dispose(view,app)
