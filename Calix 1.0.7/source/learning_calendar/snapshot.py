"""Immutable-by-convention UI snapshot; one DB read per committed mutation."""
from collections import defaultdict
from datetime import datetime,timedelta
from .models import KST

class Snapshot:
    def __init__(self, events=(), courses=()):
        self.events=sorted(events,key=lambda e:(e.completed,e.due is None,e.due or datetime.max.replace(tzinfo=KST),e.key))
        self.courses=list(courses)
        self.by_key={e.key:e for e in self.events}
        self.search={e.key:f'{e.title} {e.source_title} {e.course_name} {e.week} {e.type_label}'.casefold() for e in self.events}

    def pending(self,now=None):
        now=now or datetime.now(KST)
        return [e for e in self.events if not e.completed and (e.due is None or e.due>now)]

    def today_pending(self,now=None):
        now=now or datetime.now(KST)
        return [e for e in self.pending(now) if e.due is not None and e.due.date()==now.date()]

    def deadline_counts(self,now=None):
        now=now or datetime.now(KST);pending=self.pending(now)
        return (sum(e.due is not None and e.due.date()==now.date() for e in pending),
                sum(e.due is not None and e.due<=now+timedelta(days=7) for e in pending),len(pending))

    def filtered(self,course_id=None,query='',status=0,now=None,type_key=None):
        now=now or datetime.now(KST);query=query.casefold().strip();out=[]
        for e in self.events:
            if type_key and not (e.kind==type_key or (e.type_id is not None and type_key==f'type:{e.type_id}')):continue
            if course_id is not None and e.course_id!=course_id:continue
            if query and query not in self.search[e.key]:continue
            if status==1 and (e.completed or (e.due is not None and e.due<=now)):continue
            if status==2 and not e.completed:continue
            if status==3 and (e.completed or e.due is None or e.due>now):continue
            if status==4 and not e.starred:continue
            if status==5 and e.due is not None:continue
            if status==6 and (e.completed or e.due is None or e.due<=now or e.due.date()!=now.date()):continue
            if status==7 and (e.completed or e.due is None or not now<e.due<=now+timedelta(days=7)):continue
            out.append(e)
        return out

    @staticmethod
    def days(events):
        buckets=defaultdict(list)
        for e in events:
            if e.due:buckets[e.due.date()].append(e)
        return dict(buckets)
