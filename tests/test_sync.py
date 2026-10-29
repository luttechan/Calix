from learning_calendar.sync import CampusClient
from learning_calendar.models import Course


def test_fetch_only_expected_content(monkeypatch):
    client=CampusClient([])
    requests_seen=[]
    class Response:
        def __init__(self,body):self.body=body
        def json(self):return self.body
    def fake_get(path,params=None):
        requests_seen.append((path,params))
        if path.endswith('/courses'):
            return Response([{'id':33,'longName':'테스트 과목'}])
        if path.endswith('modules'):
            return Response([{'title':'주차학습','module_items':[
              {'content_id':10,'content_data':{'item_id':10,'title':'동영상 1',
                   'due_at':'2026-10-15T14:59:59Z','item_content_data':{'content_type':'movie'}},'completed':False},
              {'content_id':11,'content_type':'assignment','title':'그룹 안 과제'}
            ]}])
        if path.endswith('/assignments'):
            return Response([
                {'id':20,'name':'보고서','is_quiz_assignment':False,'due_at':'2026-10-17T14:59:59Z','submission':{'workflow_state':'unsubmitted'}},
                {'id':21,'name':'퀴즈','is_quiz_assignment':True}
            ])
        raise AssertionError(path)
    monkeypatch.setattr(client,'_get',fake_get)
    courses,batches,warnings=client.fetch()
    assert not warnings
    assert len(courses)==1 and courses[0].id==33
    assert len(batches[(33,'movie')])==1
    assert len(batches[(33,'assignment')])==1
    assert len(requests_seen)==3


def test_cookies_only_for_canvas():
    cookies=[{'domain':'canvas.bufs.ac.kr','name':'session','value':'x','path':'/','secure':True},
             {'domain':'attacker.invalid','name':'evil','value':'y','path':'/'}]
    client=CampusClient(cookies)
    assert 'session' in client.session.cookies.keys()
    assert 'evil' not in client.session.cookies.keys()


def test_learningx_get_includes_bearer_from_canvas_cookie(monkeypatch):
    import urllib.parse
    fake_token = 'unit-test-placeholder-token'
    cookies = [
        {'domain':'canvas.bufs.ac.kr','name':'xn_api_token','value':fake_token,'path':'/','secure':True},
        {'domain':'canvas.bufs.ac.kr','name':'_normandy_session','value':'unit-test-session','path':'/','secure':True},
    ]
    client = CampusClient(cookies)
    calls = []
    class Response:
        status_code = 200
        headers = {'content-type':'application/json'}
        def raise_for_status(self): pass
    def fake_get(url, **kwargs):
        calls.append((urllib.parse.urlsplit(url).path, kwargs.get('headers')))
        return Response()
    monkeypatch.setattr(client.session,'get',fake_get)
    client._get('/api/v1/dashboard/dashboard_cards')
    client._get('/learningx/api/v1/courses/42687/modules')
    client._get('/api/v1/courses/42687/assignment_groups')
    assert calls == [
        ('/api/v1/dashboard/dashboard_cards',None),
        ('/learningx/api/v1/courses/42687/modules',{'Authorization':'Bearer '+fake_token}),
        ('/api/v1/courses/42687/assignment_groups',None),
    ]


def test_learningx_missing_token_reports_login_needed_without_network(monkeypatch):
    from learning_calendar.sync import AuthenticationRequired
    import pytest
    client = CampusClient([{'domain':'canvas.bufs.ac.kr','name':'_normandy_session',
                            'value':'unit-test-session','path':'/','secure':True}])
    def unexpected(*args, **kwargs):
        raise AssertionError('no request allowed without bearer token')
    monkeypatch.setattr(client.session,'get',unexpected)
    with pytest.raises(AuthenticationRequired, match='xn_api_token'):
        client._get('/learningx/api/v1/courses/42687/modules')


def test_401_error_identifies_api_without_exposing_token(monkeypatch):
    from learning_calendar.sync import AuthenticationRequired
    import pytest
    fake_token = 'secret-in-memory-do-not-print'
    client = CampusClient([{'domain':'canvas.bufs.ac.kr','name':'xn_api_token',
                            'value':fake_token,'path':'/','secure':True}])
    class Response:
        status_code = 401
        headers = {'content-type':'application/json'}
    monkeypatch.setattr(client.session,'get',lambda *a,**k:Response())
    with pytest.raises(AuthenticationRequired) as exc:
        client._get('/learningx/api/v1/courses/42687/modules')
    message = str(exc.value)
    assert 'LearningX 동영상 API' in message
    assert '/learningx/api/v1/courses/42687/modules' in message
    assert fake_token not in message
