import ast,logging,re
from pathlib import Path
import pytest


@pytest.mark.parametrize('message,secrets',[
    ('Cookie: sid=synthetic-cookie-a; xn_api_token=synthetic-cookie-b\nAuthorization: Basic synthetic-basic',('synthetic-cookie-a','synthetic-cookie-b','synthetic-basic')),
    (repr({'Cookie':'sid=synthetic-first; other=synthetic-second','password':"synthetic space ' quoted",'X-CSRF-Token':'synthetic-csrf'}),('synthetic-first','synthetic-second',"synthetic space",'synthetic-csrf')),
    ("endpoint=/test?xn_api_token=synthetic-api&ok=1 password='synthetic two words' session_id=synthetic-session",('synthetic-api','synthetic two words','synthetic-session')),
])
def test_log_redaction_covers_complete_headers_and_quoted_values(message,secrets):
    # Load the actual formatter without starting the GUI or opening user logs.
    source=Path(__file__).parents[1]/'desktop/engine_logging.py';tree=ast.parse(source.read_text(encoding='utf-8'))
    definition=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='SecretSafeFormatter')
    module=ast.Module(body=[definition],type_ignores=[]);namespace={'logging':logging,'re':re}
    exec(compile(module,str(source),'exec'),namespace)
    record=logging.LogRecord('test',logging.ERROR,'test',1,message,(),None)
    formatted=namespace['SecretSafeFormatter']('%(message)s').format(record)
    assert all(secret not in formatted for secret in secrets)
    assert '[숨김]' in formatted
