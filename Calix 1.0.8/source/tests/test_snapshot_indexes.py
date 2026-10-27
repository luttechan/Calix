from datetime import datetime,timedelta
from learning_calendar.models import Event,KST
from learning_calendar.snapshot import Snapshot


def test_indexed_filters_preserve_all_statuses_and_order():
    now=datetime.now(KST)
    rows=[Event(f'{kind}:{course}:{i}',course,f'과목 {course}',kind,f'일정 {i}',(now+timedelta(days=i-3)).isoformat(),i%3==0) for kind in ('assignment','movie') for course in (1,2) for i in range(8)]
    snapshot=Snapshot(rows)
    for course in (None,1,2,99):
        for kind in (None,'assignment','movie','missing'):
            for status in range(8):
                reference=Snapshot([e for e in rows if (course is None or e.course_id==course) and (kind is None or e.kind==kind)])
                assert snapshot.filtered(course,'일정',status,now,kind)==reference.filtered(query='일정',status=status,now=now)


def test_custom_type_indexes_are_also_available_under_original_kind():
    event=Event('manual:1',0,'개인 일정','assignment','시험',None,False,type_id=7)
    snapshot=Snapshot([event])
    assert snapshot.filtered(type_key='type:7')==[event]
    assert snapshot.filtered(type_key='assignment')==[event]
    assert snapshot.filtered(course_id=99,type_key='type:7')==[]
