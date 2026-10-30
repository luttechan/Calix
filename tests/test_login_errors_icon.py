import ssl
from pathlib import Path
import pytest
import requests
from PySide6.QtWidgets import QApplication
from learning_calendar.login import LoginValidation
from learning_calendar.sync import CampusClient,AuthenticationRequired,LearningXAuthenticationRequired


@pytest.mark.parametrize('error,message',[
    (AuthenticationRequired('expired'),'만료'),
    (requests.ConnectionError('offline'),'연결'),
    (FileNotFoundError('TLS policy missing'),'연결'),
    (requests.exceptions.SSLError('certificate'),'연결'),
    (ValueError('unexpected response'),'연결'),
])
def test_login_validation_reports_expired_only_for_authentication(error,message,monkeypatch):
    def fail(*args,**kwargs):raise error
    monkeypatch.setattr(CampusClient,'_get',fail)
    QApplication.instance() or QApplication([])
    task=LoginValidation([]);failed=[];checked=[]
    task.failed.connect(failed.append);task.checked.connect(checked.append);task.run()
    assert not checked and len(failed)==1 and message in failed[0]
    if message=='연결':assert '만료' not in failed[0]


def test_movie_authentication_failure_preserves_canvas_assignments(monkeypatch):
    client=CampusClient([])
    class Response:
        def json(self):return [{'id':1,'longName':'과목'}]
    def get(path,params=None):
        if path.endswith('/modules'):raise LearningXAuthenticationRequired('token expired')
        return Response()
    def paginated(path,params=None,**kwargs):
        if path.endswith('/courses'):return [{'id':1,'name':'과목'}]
        if path.endswith('/modules'):raise LearningXAuthenticationRequired('token expired')
        if path.endswith('/assignments'):return [{'id':2,'name':'과제'}]
        return []
    monkeypatch.setattr(client,'_get',get);monkeypatch.setattr(client,'_paginated',paginated)
    courses,batches,warnings=client.fetch()
    assert (1,'movie') not in batches and batches[(1,'assignment')][0].title=='과제'
    assert warnings
    client.session.close()


def test_canvas_forbidden_is_permission_error_not_expired_session(monkeypatch):
    client=CampusClient([]);response=requests.Response();response.status_code=403
    monkeypatch.setattr(client.session,'get',lambda *a,**k:response)
    with pytest.raises(requests.HTTPError):client._get('/api/v1/courses/1/assignment_groups')
    client.session.close()


def test_icon_is_available_at_taskbar_and_high_dpi_sizes():
    from learning_calendar.app_identity import app_icon,apply_app_icon
    app=QApplication.instance() or QApplication([]);apply_app_icon(app)
    icon=app_icon();sizes={s.width() for s in icon.availableSizes()}
    assert {16,24,32,48,64,128,256}<=sizes
    assert not app.windowIcon().isNull()
    for n in [16,24,32,48,256]:assert not icon.pixmap(n,n).isNull()


def test_tls_context_has_working_certificate_policy():
    context=ssl.create_default_context()
    assert context.check_hostname and context.verify_mode==ssl.CERT_REQUIRED
