import json
from types import SimpleNamespace
from urllib.parse import urlsplit
import pytest
from PySide6.QtCore import QUrl
from PySide6.QtQml import QJSEngine
from PySide6.QtWidgets import QApplication
from learning_calendar.login import CampusLoginDialog
from learning_calendar import preferences


@pytest.mark.parametrize('location,action,allowed',[
    ('https://canvas.bufs.ac.kr/login','https://canvas.bufs.ac.kr/login',True),
    ('https://eclass.bufs.ac.kr/login','https://eclass.bufs.ac.kr/login',True),
    ('https://attacker.invalid/login','https://attacker.invalid/login',False),
    ('https://canvas.bufs.ac.kr/login','https://attacker.invalid/collect',False),
    ('https://canvas.bufs.ac.kr:8443/login','https://canvas.bufs.ac.kr:8443/login',False),
])
def test_credentials_are_not_injected_after_navigation_or_into_foreign_form(monkeypatch,location,action,allowed):
    app=QApplication.instance() or QApplication([]);scripts=[]
    monkeypatch.setattr(preferences,'read_account',lambda:'synthetic-id')
    monkeypatch.setattr(preferences,'read_password',lambda *_:'synthetic-password')
    dialog=CampusLoginDialog();dialog._browser_started=True
    # The Python check sees the school. The page can change before execution.
    dialog.view=SimpleNamespace(url=lambda:QUrl('https://canvas.bufs.ac.kr/login'))
    dialog.page=SimpleNamespace(runJavaScript=scripts.append)
    dialog.fill_form();assert len(scripts)==1 and dialog._password==''
    urls={}
    for url in (location,action):
        p=urlsplit(url);urls[url]=dict(protocol=p.scheme+':',hostname=p.hostname,port=str(p.port or ''),username=p.username or '',password=p.password or '')
    engine=QJSEngine()
    setup='''var urls=%s;function URL(value){return urls[value];}var location={href:%s};var sink=[];function Event(){}function HTMLInputElement(type){this.type=type;this.form={action:%s};this.dispatchEvent=function(){};}Object.defineProperty(HTMLInputElement.prototype,'value',{set:function(v){sink.push(v);}});var fields=[new HTMLInputElement('text'),new HTMLInputElement('password')];var document={querySelector:function(){return fields[1];},querySelectorAll:function(){return fields;}};'''%(json.dumps(urls),json.dumps(location),json.dumps(action))
    assert not engine.evaluate(setup).isError()
    result=engine.evaluate(scripts[0]);assert not result.isError(),result.toString()
    assert engine.globalObject().property('sink').toVariant()==(['synthetic-id','synthetic-password'] if allowed else [])
    dialog.view=None;dialog.page=None;dialog.dispose();dialog.deleteLater();app.processEvents()
