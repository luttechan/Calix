import sys
from types import SimpleNamespace
import pytest
from learning_calendar.parsers import safe_url
from learning_calendar.sync import CampusClient
from learning_calendar.preferences import store_account,read_account,SERVICE,LEGACY_SERVICE,ACCOUNT_KEY


@pytest.mark.parametrize('url',[
    'https://attacker.invalid/learningx/api/v1/token',
    '//attacker.invalid/learningx/api/v1/token',
    'http://canvas.bufs.ac.kr/api/v1/users/self/profile',
    'https://canvas.bufs.ac.kr:8443/learningx/api/v1/token',
    'https://name:password@canvas.bufs.ac.kr/api/v1/users/self/profile',
    'https://canvas.bufs.ac.kr:invalid/path',
    'https://[broken/path',
])
def test_untrusted_request_never_sends_cookies_or_bearer(url,monkeypatch):
    client=CampusClient([dict(name='xn_api_token',value='synthetic-only',domain='canvas.bufs.ac.kr')])
    def forbidden(*args,**kwargs):raise AssertionError('untrusted request was sent')
    monkeypatch.setattr(client.session,'get',forbidden)
    assert safe_url(url)==''
    with pytest.raises(ValueError):client._get(url)
    client.session.close()


def test_account_removal_clears_current_and_legacy_credentials(monkeypatch):
    import keyring
    rows={(SERVICE,ACCOUNT_KEY):'synthetic-id',(LEGACY_SERVICE,ACCOUNT_KEY):'older-id',(SERVICE+'/password','synthetic-id'):'secret',(LEGACY_SERVICE+'/password','older-id'):'legacy-secret',(LEGACY_SERVICE,'older-id'):'older-secret'}
    monkeypatch.setattr(keyring,'get_password',lambda service,key:rows.get((service,key)))
    def remove(service,key):
        if (service,key) not in rows:raise keyring.errors.PasswordDeleteError()
        del rows[service,key]
    monkeypatch.setattr(keyring,'delete_password',remove)
    store_account('')
    assert read_account()=='' and rows=={}
