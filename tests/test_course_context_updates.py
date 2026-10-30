from types import SimpleNamespace
import time
import pytest
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from learning_calendar.models import Course
from learning_calendar.sync import CampusClient


@pytest.fixture(scope='module')
def app():return QApplication.instance() or QApplication([])


def cleanup(widget,app):
    if hasattr(widget,'dispose'):widget.dispose()
    else:widget.close()
    widget.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()


def test_course_context_used_and_restored_on_failure(monkeypatch):
    client=CampusClient([]);seen=[]
    def pages(path,*args,**kwargs):
        seen.append((path,client.session.headers['Referer']))
        raise ValueError('synthetic')
    monkeypatch.setattr(client,'_paginated',pages)
    with pytest.raises(ValueError):client._course_movies(Course(12,'과목'))
    assert seen==[('/learningx/api/v1/courses/12/modules','https://canvas.bufs.ac.kr/courses/12')]
    assert client.session.headers['Referer']=='https://canvas.bufs.ac.kr/'
    assert client.session.headers['Cache-Control']=='no-cache'
    client.session.close()


@pytest.mark.parametrize('modules',[
    [{'title':'1주차'}],
    [{'module_items':[{'content_data':{'item_content_type':'commons'}}]}],
])
def test_incomplete_course_outline_does_not_replace_video_batch(monkeypatch,modules):
    client=CampusClient([])
    monkeypatch.setattr(client,'_paginated',lambda path,*args,**kwargs:modules if path.endswith('/modules') else [])
    batches,warnings=client._fetch_course(Course(12,'과목'),lambda *_:None)
    assert (12,'movie') not in batches and (12,'assignment') in batches and warnings
    assert not client.course_checks[12]['videos_verified']
    client.session.close()


def test_empty_published_week_is_valid(monkeypatch):
    client=CampusClient([])
    monkeypatch.setattr(client,'_paginated',lambda *args,**kwargs:[{'module_items':[]}])
    assert client._course_movies(Course(12,'과목'))==[]
    client.session.close()
















