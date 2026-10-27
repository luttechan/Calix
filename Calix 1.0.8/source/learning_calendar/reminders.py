"""Local, opt-in reminders. No network and no notifications while disabled."""
from datetime import datetime,timedelta
from .models import KST

class DueReminders:
    def __init__(self):self.day=None;self.seen=set()
    def pending(self,events,now=None):
        now=now or datetime.now(KST)
        if self.day!=now.date():self.day=now.date();self.seen.clear()
        result=[]
        for event in events:
            marker=(event.key,event.due_at)
            if not event.completed and event.due and now<=event.due<=now+timedelta(minutes=15) and marker not in self.seen:
                self.seen.add(marker);result.append(event)
        if len(self.seen)>20000:self.seen=set(list(self.seen)[-10000:])
        return result
