from dataclasses import replace
from datetime import datetime,timedelta,date
import hashlib
import json
from types import SimpleNamespace
import pytest
from PySide6.QtCore import Qt,QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from learning_calendar.models import Event,Course,KST,deadline_display
from learning_calendar.sync import CampusClient
from learning_calendar.storage import Store
from learning_calendar.updates import parse_release,version_key,trusted_download

@pytest.fixture(scope='module')
def app():return QApplication.instance() or QApplication([])

def dispose(widget,app):
    widget.close();widget.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()





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

