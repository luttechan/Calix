from types import SimpleNamespace
import pytest
from PySide6.QtWidgets import QApplication
from learning_calendar.models import Course
from learning_calendar.parsers import movie_completion
from learning_calendar.login import LoginValidation

@pytest.mark.parametrize('item,done',[
    ({'completed':True},True),({'completed':False},False),({'completed':'false'},False),
    ({'completed':'true'},True),({'completed':False,'attendance_status':'attendance'},True),
    ({'attendance_status':'late'},True),({'attendance_status':'excused'},True),
    ({'attendance_status':'none'},False),({'attendance_status':'absent'},False)])
def test_school_video_completion_fields(item,done):assert movie_completion(item) is done

def test_missing_video_completion_is_not_guessed():
    assert movie_completion({}) is None

@pytest.mark.parametrize('failed_course',[None,6])
def test_login_checks_every_course_and_does_not_accept_first_success(monkeypatch,failed_course):
    import learning_calendar.sync as sync
    app=QApplication.instance() or QApplication([]);seen=[]
    class Client:
        _learningx_token='synthetic-token'
        session=SimpleNamespace(close=lambda:None)
        def __init__(self,*args):pass
        def _list_courses(self):return [Course(i,f'과목 {i}') for i in range(1,8)]
        def _course_movies(self,course):
            from learning_calendar.parsers import parse_movies
            return parse_movies(course,self._paginated(f'/learningx/api/v1/courses/{course.id}/modules'))
        def _paginated(self,path,*args,**kwargs):
            cid=int(path.split('/')[-2]);seen.append(cid)
            if cid==failed_course:raise sync.LearningXAuthenticationRequired('test')
            return [{'module_items':[{'completed':True,'content_data':{'item_id':cid,'item_content_data':{'content_type':'movie'}}}]}]
        def _get(self,path):
            return SimpleNamespace(json=lambda:{'id':1} if path.endswith('/profile') else [{'label':'주차학습','html_url':f'/courses/{failed_course}/external_tools/1'}])
    monkeypatch.setattr(sync,'CampusClient',Client);task=LoginValidation([]);results=[];task.checked.connect(results.append);task.run()
    assert seen==list(range(1,8)) and results[0]['checked_courses']==7
    assert results[0]['token_valid']==(failed_course is None)
    assert results[0]['failed_courses']==([] if failed_course is None else [failed_course])
    if failed_course:assert results[0]['course_id']==failed_course and '/courses/6/' in results[0]['learningx_url']

def test_cookie_presence_alone_is_not_reported_as_verified():
    from learning_calendar.browser_service import BrowserService
    calls=[]
    fake=SimpleNamespace(closing=False,dialog=SimpleNamespace(movies_verified=False,_has_token=lambda:True),_save=lambda rows:True,send=lambda *args,**kwargs:calls.append(kwargs))
    BrowserService.authenticated(fake,[]);assert calls==[{'movies_ready':False}]
    fake.dialog.movies_verified=True;BrowserService.authenticated(fake,[]);assert calls[-1]=={'movies_ready':True}

def test_partial_course_failure_keeps_the_token_that_other_courses_verified():
    from learning_calendar.login import CampusLoginDialog
    from PySide6.QtCore import QCoreApplication,QEvent
    app=QApplication.instance() or QApplication([]);dialog=CampusLoginDialog();dialog._browser_started=True
    dialog.view=SimpleNamespace(setUrl=lambda url:None,stop=lambda:None,deleteLater=lambda:None)
    key=('canvas.bufs.ac.kr','xn_api_token','/');dialog.rows[key]={'name':'xn_api_token','value':'synthetic','domain':'canvas.bufs.ac.kr'}
    dialog._checked(dict(course_id=6,token_valid=False,verified_courses=6,learningx_url='https://canvas.bufs.ac.kr/courses/6/external_tools/1'))
    assert key in dialog.rows and not dialog.movies_verified
    dialog.dispose();dialog.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
