import pytest
from learning_calendar.attendance import project
from learning_calendar.models import Course

@pytest.mark.parametrize('state',['excused','absent'])
def test_excused_and_absent_preserved_for_classes_and_videos(state):
    rows=project(Course(1,'수업'),{
        'lessons':[{'week_position':1,'lessons':[{'lesson_position':1,'class_date':'2026-11-20'}]}],
        'lessons/attendances':[{'week_position':1,'lesson_position':1,'attendance_status':state}],
        'attendance_items':{'attendance_items':[{'item_id':11,'title':'영상','use_attendance':True}]},
        'attendance_items/summary':{'attendance_summaries':{'11':{'attendance_status':state}}},
    })
    assert [r['status'] for r in rows]==[state,state]
    assert [r['source'] for r in rows]==['lesson','item']
