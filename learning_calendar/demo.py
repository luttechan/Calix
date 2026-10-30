from datetime import datetime,timedelta
from .models import Course, Event, KST

def data():
    """Entirely synthetic examples; no HAR or real account data is distributed."""
    now=datetime.now(KST)
    course1=Course(901,'비즈니스 일본어')
    course2=Course(902,'통번역 연습')
    entries=[]
    for ix in range(14):
        kind = 'movie' if ix%3 else 'assignment'
        due = (now+timedelta(days=ix-3)).replace(hour=23,minute=59,second=0,microsecond=0)
        entries.append(Event(key=f'{kind}:demo:{ix}',course_id=course1.id if ix%2 else course2.id,
          course_name=course1.name if ix%2 else course2.name,kind=kind,
          title=f'{ix+1}주차 {"동영상 학습" if kind=="movie" else "일반 과제"}',
          due_at=due.isoformat(),completed=ix<3,week=f'{ix+1}주차'))
    return [course1,course2],{(c.id,k):[e for e in entries if e.course_id==c.id and e.kind==k]
                         for c in (course1,course2) for k in ('movie','assignment')}
