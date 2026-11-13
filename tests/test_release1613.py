import sys
from pathlib import Path
from uuid import uuid4
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"desktop"))
from engine_api import EngineAPI
from learning_calendar.models import Course

@pytest.fixture
def api(tmp_path):
    value=EngineAPI(tmp_path)
    value.dispatch("security.setup",dict(password="Calix bulk grading phrase!",policy=dict(main=False,timetable=False,grades=False,idle_minutes=5)))
    yield value
    value.close()

def row(title="과목",**extra):
    return dict(id="manual:"+uuid4().hex,title=title,credits=3,grade="A+",category="전공",excluded=False,**extra)

def save(api,items,deleted=None,scale="4.5",revision=None):
    current=api.dispatch("grades.read",{})
    return api.dispatch("grades.save_all",dict(items=items,deleted=deleted or [],scale=scale,revision=current["revision"] if revision is None else revision))

def test_bulk_save_updates_adds_deletes_and_scale_in_one_request(api):
    first=row("첫 과목");second=row("두 번째 과목");second.update(credits=2,grade="B")
    result=save(api,[first,second]);assert result["summary"]["gpa"]=="3.90"
    third=row("P 과목");third.update(credits=2,grade="P")
    first.update(credits=4,grade="A")
    result=save(api,[first,third],[second["id"]],scale="4.0")
    assert result["scale"]=="4.0" and result["summary"]["gpa"]=="4.00" and result["summary"]["earned_credits"]==6
    assert {item["id"] for item in result["items"]}=={first["id"],third["id"]}

def test_invalid_row_rolls_back_whole_batch(api):
    first=row("원본");save(api,[first]);before=api.dispatch("grades.read",{})
    changed=dict(first,credits=5);invalid=row("오류");invalid["credits"]=-1
    with pytest.raises(ValueError):save(api,[changed,invalid],scale="4.3")
    assert api.dispatch("grades.read",{})==before and not api.store.db.in_transaction

def test_database_write_failure_rolls_back_prior_rows_and_deletion(api):
    first=row("유지");removed=row("삭제 예정");save(api,[first,removed]);before=api.dispatch("grades.read",{})
    api.store.db.execute("CREATE TRIGGER reject_grade BEFORE INSERT ON grade_items WHEN NEW.title='FAIL' BEGIN SELECT RAISE(ABORT,'injected failure'); END")
    with pytest.raises(Exception,match="injected failure"):
        save(api,[dict(first,title="바뀌면 안 됨"),row("FAIL")],[removed["id"]],scale="4.3")
    assert api.dispatch("grades.read",{})==before and not api.store.db.in_transaction

def test_stale_revision_cannot_overwrite_other_changes(api):
    first=row();initial=save(api,[first]);api.dispatch("grades.save",dict(first,credits=5))
    with pytest.raises(ValueError,match="변경되었습니다"):
        save(api,[dict(first,credits=2)],revision=initial["revision"])
    assert api.dispatch("grades.read",{})["items"][0]["credits"]==5

@pytest.mark.parametrize("value",[True,float('nan'),float('inf'),"3",-1,30.5,1.1])
def test_invalid_credit_types_never_commit(api,value):
    item=row();item['credits']=value
    with pytest.raises(ValueError):save(api,[item])
    assert not api.dispatch("grades.read",{})['items']

def test_duplicate_ids_and_linked_deletions_are_rejected(api):
    item=row()
    with pytest.raises(ValueError):save(api,[item,item])
    api.store.apply_batch([Course(901,"수업")],{})
    api.store.add_timetable(901,0,"09:00","10:00",title="수업")
    current=api.dispatch("grades.read",{});linked=current["items"][0]
    with pytest.raises(ValueError):save(api,[],[linked["id"]])
    assert api.dispatch("grades.read",{})==current

def test_new_timetable_rows_are_not_lost_by_saving_an_existing_draft(api):
    item=row();initial=save(api,[item])
    api.store.apply_batch([Course(901,"수업")],{});api.store.add_timetable(901,0,"09:00","10:00",title="수업")
    result=save(api,[dict(item,credits=4)],revision=initial["revision"])
    assert len(result["items"])==2 and any(row["linked"] for row in result["items"])

def test_bulk_save_still_requires_password(tmp_path):
    value=EngineAPI(tmp_path)
    try:
        with pytest.raises(ValueError,match="비밀번호를 설정"):
            value.dispatch("grades.save_all",dict(items=[],scale="4.5",revision=""))
    finally:value.close()
