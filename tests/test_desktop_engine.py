import sys,json,subprocess
from pathlib import Path
from dataclasses import replace
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'desktop'))
from engine_api import EngineAPI
from learning_calendar.models import Course,Event

@pytest.fixture
def engine(tmp_path):
    api=EngineAPI(tmp_path);rows=[Event('a',1,'수업','assignment','과제','2026-11-03T23:59:00+09:00',False),Event('m',1,'수업','movie','영상',None,True)]
    api.store.apply_batch([Course(1,'수업')],{(1,'assignment'):rows[:1],(1,'movie'):rows[1:]});yield api;api.close()

def test_bootstrap_json_never_loads_qt_widgets_or_private_diary(engine):
    data=engine.dispatch('bootstrap',{});json.dumps(data,ensure_ascii=False)
    assert data['version']=='1.4.0' and len(data['events'])==2 and not data['tasks'] and engine.vault is None
    assert 'cookies' not in data and 'password' not in data

def test_explicit_checklist_import_edits_survive_refresh(engine):
    assert engine.dispatch('checklist.import',{'keys':['a']})==1
    tasks=engine.bootstrap()['tasks'];assert len(tasks)==1 and tasks[0]['source_key']=='a'
    engine.dispatch('checklist.save',{'id':tasks[0]['id'],'field':'role','value':'발표'});assert engine.bootstrap()['tasks'][0]['role']=='발표'
    assert engine.dispatch('checklist.import',{'keys':['a']})==0
    engine.dispatch('checklist.delete',{'id':tasks[0]['id']});assert not engine.bootstrap()['tasks']

def test_school_event_edits_do_not_change_authentic_completion(engine):
    engine.dispatch('event.save',{'key':'a','title':'새 이름','note':'메모','type_id':None});assert engine.event('a').title=='새 이름'
    with pytest.raises(ValueError):engine.dispatch('event.complete',{'key':'a','completed':True})
    assert not engine.event('a').completed

def test_manual_event_timetable_and_preferences_validation(engine):
    kind=engine.bootstrap()['types'][0]['id'];key=engine.dispatch('event.add',{'title':'개인 할 일','type_id':kind,'due_at':None})
    engine.dispatch('event.complete',{'key':key,'completed':True});assert engine.event(key).completed
    sid=engine.dispatch('timetable.save',{'course_id':1,'day':0,'start_time':'09:00','end_time':'10:30','professor':'교수','room':'A201','color':'#AA5588'})
    engine.dispatch('timetable.off',{'days':[0]});assert engine.bootstrap()['offDays']==[0] and engine.bootstrap()['sessions'][0]['professor']=='교수'
    with pytest.raises(ValueError):engine.dispatch('timetable.off',{'days':[True]})
    with pytest.raises(ValueError):engine.dispatch('preferences.save',{'theme':'javascript'})
    engine.dispatch('preferences.save',{'theme':'dark','glass':False});assert engine.bootstrap()['preferences']['theme']=='dark'

def test_diary_rich_text_and_secret_storage_are_preserved(engine):
    value=dict(date='2026-10-30',title='일기',body='본문',html='<p><strong>본문</strong></p>');key=engine.dispatch('diary.save',{'value':value})
    assert engine.dispatch('diary.read',{'id':key})['html']==value['html']
    engine.dispatch('vault.unlock',{'password':'a-strong-test-password'});secret=engine.dispatch('diary.save',{'secret':True,'value':value})
    assert engine.dispatch('diary.read',{'secret':True,'id':secret})['title']=='일기'
    engine.dispatch('vault.lock',{})
    with pytest.raises(ValueError):engine.dispatch('diary.read',{'secret':True,'id':secret})
    assert '일기'.encode() not in (engine.folder/'private-diary.db').read_bytes()

def test_backend_rejects_unknown_methods_and_store_path_escape(engine):
    with pytest.raises(ValueError):engine.dispatch('__import__',{})
    with pytest.raises(ValueError):engine.switch_store(engine.folder.parent/'outside.db')

def test_special_preferences_survive_bootstrap_and_year_navigation(engine):
    engine.dispatch('special.save',{'catholic':False,'birthday':True})
    assert engine.bootstrap()['preferences']['birthday'] is True
    dates=engine.dispatch('calendar.year',{'year':2028})
    assert dates['specialDates']['2028-06-27']=='클로네 생일'
    with pytest.raises(ValueError):engine.dispatch('calendar.year',{'year':True})
    with pytest.raises(ValueError):engine.dispatch('special.save',{'catholic':'false','birthday':True})

def test_manual_deadline_changes_and_delete_do_not_affect_school_events(engine):
    kind=engine.bootstrap()['types'][0]['id']
    key=engine.dispatch('event.add',{'title':'개인 일정','type_id':kind})
    engine.dispatch('event.save',{'key':key,'title':'수정 일정','due_at':'2026-12-01T23:59:00+09:00','note':'보존'})
    assert engine.event(key).due_at.startswith('2026-12-01')
    engine.dispatch('event.delete',{'key':key})
    assert len(engine.bootstrap()['events'])==2
    with pytest.raises(ValueError):engine.dispatch('event.delete',{'key':'a'})

def test_installer_helper_rejects_arbitrary_file_and_digest(tmp_path):
    from engine_utility import install
    path=tmp_path/'Calix-Setup.exe';path.write_bytes(b'not an installer')
    assert install(path,'0'*64,1)==2

def test_stdio_round_trip_and_clean_exit_use_temporary_data(tmp_path):
    requests=[dict(id=1,method='bootstrap',params={}),dict(id=2,method='quit',params={})]
    result=subprocess.run([sys.executable,'-B',str(ROOT/'desktop/engine_main.py'),'--data-dir',str(tmp_path)],input=''.join(json.dumps(r)+'\n' for r in requests),capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert result.returncode==0,result.stderr
    messages=[json.loads(line) for line in result.stdout.splitlines()];assert next(r for r in messages if r.get('id')==1)['result']['version']=='1.4.0'
