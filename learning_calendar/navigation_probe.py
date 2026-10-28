"""Isolated click-to-paint check using synthetic events, never account data."""
import json
import time
from datetime import datetime,timedelta
from PySide6.QtCore import QObject,QEvent,QTimer,Qt,QPoint,QPointF
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication,QWidget
from .models import Course,Event,KST
from .snapshot import Snapshot


class NavigationProbe(QObject):
    def __init__(self,window,output,count=250):
        super().__init__(window);self.window=window;self.output=output;self.samples=[];self.active=None;self.startup_ms=None
        window.installEventFilter(self)
        self.pages=iter((2,0,1,2,3,'diary','home',0,1,2,3,'diary','home'));now=datetime.now(KST)
        rows=[Event(f'{kind}:{i%20+1}:{i}',i%20+1,f'검사 과목 {i%20+1}',kind,f'검사 일정 {i}',(now+timedelta(days=i%20+1)).isoformat(),False) for kind in ('assignment','movie') for i in range(min(10000,max(1,count)))]
        courses=[Course(i,f'검사 과목 {i}') for i in range(1,21)];window.store.apply_batch(courses,{})
        window.snapshot=Snapshot(rows,courses)
        window._sessions=[dict(id=i+1,course_id=i+1,day=i%5,start_time='09:00' if i<5 else '13:00',end_time='10:30' if i<5 else '14:30',professor=f'검사 교수 {i+1}',room='A201',color='#7582E6') for i in range(6)]
        window._reload_course_filter();window.refresh()
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self.timeout)
        QTimer.singleShot(150,self.next)

    def next(self):
        try:page=next(self.pages)
        except StopIteration:self.finish();return
        w=self.window
        target=w.home if page=='home' else w.diary if page=='diary' else w.assignment_list if page==2 else w.video_list if page==1 else w.calendar if page==0 else w.timetable
        self.active=dict(page=page,started=time.perf_counter(),target=target,painted=False)
        QApplication.instance().installEventFilter(self);self.timer.start(4000)
        button=w.home_nav if page=='home' else w.diary_nav if page=='diary' else w.nav[page]
        center=button.rect().center();local=QPointF(center);global_pos=QPointF(button.mapToGlobal(center))
        # Deliver the same press/release path without bundling Qt's test tools.
        for kind,buttons in ((QEvent.Type.MouseButtonPress,Qt.MouseButton.LeftButton),(QEvent.Type.MouseButtonRelease,Qt.MouseButton.NoButton)):
            event=QMouseEvent(kind,local,global_pos,Qt.MouseButton.LeftButton,buttons,Qt.KeyboardModifier.NoModifier)
            QApplication.sendEvent(button,event)
        self.active['handler_ms']=(time.perf_counter()-self.active['started'])*1000
        target.update()

    def eventFilter(self,watched,event):
        if watched is self.window and event.type()==QEvent.Type.Paint and self.window.isVisible() and self.startup_ms is None:
            self.startup_ms=-1;QTimer.singleShot(0,self.startup_ready)
        sample=self.active
        if sample and event.type()==QEvent.Type.Paint and not sample['painted'] and isinstance(watched,QWidget) and (watched is sample['target'] or sample['target'].isAncestorOf(watched)):
            sample['painted']=True
            # Runs after paintEvent returns, including its native text rendering.
            QTimer.singleShot(0,self.painted)
        return False

    def startup_ready(self):
        from .diagnostics import process_age_ms
        self.startup_ms=process_age_ms()

    def painted(self):
        if not self.active:return
        sample=self.active;elapsed=(time.perf_counter()-sample['started'])*1000
        QApplication.instance().removeEventFilter(self);self.timer.stop();self.active=None
        selected='home' if self.window.main_stack.currentIndex()==0 else 'diary' if self.window.main_stack.currentIndex()==2 else self.window.tabs.currentIndex()
        self.samples.append(dict(page=sample['page'],click_to_paint_ms=round(elapsed,2),handler_ms=round(sample['handler_ms'],2),selected=selected))
        QTimer.singleShot(180,self.next)

    def timeout(self):
        target=self.active['target']
        origin=target.mapTo(self.window,QPoint(0,0))
        self.samples.append(dict(page=self.active['page'],error='paint timeout',visible=target.isVisible(),updates=target.updatesEnabled(),region=target.visibleRegion().boundingRect().getRect(),position=[origin.x(),origin.y()],geometry=[target.width(),target.height()],stack=self.window.main_stack.currentIndex()))
        self.timer.stop();QApplication.instance().removeEventFilter(self);self.active=None;QTimer.singleShot(180,self.next)

    def finish(self):
        QApplication.instance().removeEventFilter(self)
        from .diagnostics import memory_usage
        result=dict(target_ms=50,items=len(self.window.snapshot.events),courses=len(self.window.snapshot.courses),timetable_sessions=len(self.window._sessions),startup_ms=self.startup_ms,memory=memory_usage(),qt_platform=QApplication.platformName(),samples=self.samples,passed=len(self.samples)==13 and all('error' not in s and s['click_to_paint_ms']<50 and s['page']==s['selected'] for s in self.samples))
        self.output.parent.mkdir(parents=True,exist_ok=True);self.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
        self.window.dispose();QApplication.instance().exit(0 if result['passed'] else 1)
