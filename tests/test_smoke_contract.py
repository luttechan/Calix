import json,os,subprocess,sys
from pathlib import Path

def test_offline_release_smoke_accepts_calendar_geometry(tmp_path):
    report=tmp_path/'smoke.json';env=os.environ.copy();env['QT_QPA_PLATFORM']='offscreen';env['LOCALAPPDATA']=str(tmp_path/'local');env['PYTHONPATH']=os.pathsep.join(sys.path)
    result=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve().parents[1]/'main.py'),'--smoke-test',str(report)],env=env,capture_output=True,text=True,timeout=40)
    assert result.returncode==0,result.stderr[-2000:]
    data=json.loads(report.read_text(encoding='utf-8'))
    for key in ('compact_calendar_chips','calendar_nov29_overlay_matches','calendar_full_width_default','home_available','timetable_available','diary_available','login_available'):
        assert data[key] is True,(key,data)
