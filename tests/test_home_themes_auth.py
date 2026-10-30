"""Regression tests for the home flow and the reported cookie failure."""
from datetime import datetime,timedelta
import pytest
from PySide6.QtCore import QCoreApplication,QEvent,Qt
from PySide6.QtWidgets import QApplication,QWidget
from learning_calendar.cookies import canvas_session_available,applies_to_canvas
from learning_calendar.sync import CampusClient,LearningXTokenMissing
from learning_calendar.models import Event,Course,KST
from learning_calendar.snapshot import Snapshot







def test_canvas_cookie_is_sufficient_without_movie_token():
    rows=[{'name':'_normandy_session','domain':'.canvas.bufs.ac.kr','path':'/','value':'test-session','secure':True}]
    assert canvas_session_available(rows)
    assert not any(r['name']=='xn_api_token' for r in rows)
    assert not canvas_session_available([{'name':'_csrf_token','domain':'canvas.bufs.ac.kr','value':'x'}])

def test_parent_domain_cookie_is_preserved_but_unrelated_domains_are_not():
    rows=[{'name':'_normandy_session','domain':'.bufs.ac.kr','value':'parent-session','path':'/','secure':True},
          {'name':'sso','domain':'eclass.bufs.ac.kr','value':'not-for-canvas','path':'/'}]
    client=CampusClient(rows)
    try:
        assert '_normandy_session' in client.session.cookies.keys()
        assert 'sso' not in client.session.cookies.keys()
        assert applies_to_canvas('.bufs.ac.kr')
        assert not applies_to_canvas('fakecanvas.bufs.ac.kr')
    finally:client.session.close()

def test_duplicate_domain_cookies_do_not_send_duplicate_session_headers():
    rows=[{'name':'_normandy_session','domain':'.bufs.ac.kr','value':'parent','path':'/'},
          {'name':'_normandy_session','domain':'.canvas.bufs.ac.kr','value':'host','path':'/'},
          {'name':'_normandy_session','domain':'canvas.bufs.ac.kr','value':'latest','path':'/'}]
    client=CampusClient(rows)
    try:
        assert len(client.session.cookies)==1
        assert client.session.cookies.get('_normandy_session')=='latest'
    finally:client.session.close()

def test_missing_learningx_token_still_fetches_assignments(monkeypatch):
    client=CampusClient([])
    class Response:
        def json(self):return [{'id':1,'longName':'과목'}]
    def fake_get(path,params=None):
        if path.endswith('/modules'):raise LearningXTokenMissing('token missing')
        return Response()
    def paginate(path,params=None,**kwargs):
        if path.endswith('/courses'):return [{'id':1,'name':'과목'}]
        if path.endswith('/modules'):raise LearningXTokenMissing('token missing')
        if path.endswith('/assignments'):return [{'id':2,'name':'보고서'}]
        return []
    monkeypatch.setattr(client,'_get',fake_get);monkeypatch.setattr(client,'_paginated',paginate)
    courses,batches,warnings=client.fetch()
    assert batches[(1,'assignment')][0].title=='보고서'
    assert (1,'movie') not in batches and warnings
    client.session.close()








