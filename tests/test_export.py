from learning_calendar.models import Event
from learning_calendar.exporters import export_ics,_fold


def test_icalendar_includes_only_dates(tmp_path):
    items=[
      Event('movie:1:1',1,'Course','movie','Video','2026-10-11T14:59:59Z',False),
      Event('assignment:1:2',1,'Course','assignment','Essay',None,False),
      Event('movie:1:3',1,'Course','movie','Finished','2026-10-12T14:59:59Z',True)
    ]
    path=tmp_path/'output.ics'
    count=export_ics(items,path,False)
    assert count==1
    content=path.read_bytes()
    assert content.count(b'BEGIN:VEVENT')==1
    assert b'DTSTART:20261011T145959Z' in content
    assert content.startswith(b'BEGIN:VCALENDAR\r\n')


def test_long_unicode_line_is_validly_folded():
    lines=_fold('SUMMARY:'+'한글 가나 カタカナ'*30)
    assert len(lines)>1
    assert all(len(x.encode('utf-8'))<=75 for x in lines)
    assert all(x.startswith(' ') for x in lines[1:])
    assert lines[0]+''.join(x[1:] for x in lines[1:])=='SUMMARY:'+'한글 가나 カタカナ'*30
