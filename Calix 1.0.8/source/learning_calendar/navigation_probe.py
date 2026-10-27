"""Isolated click-to-paint check using synthetic events, never account data."""
import json
import time
from datetime import datetime,timedelta
from PySide6.QtCore import QObject,QEvent,QTimer,Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from .models import Course,Event,KST
from .snapshot import Snapshot


class NavigationProbe(QObject):
    def __init__(self,window,output,count=5000):
        super().__init__(window);self.window=window;self.output=output;self.samples=[];self.active=None
        self.pages=iter((2,0,1,2,3,2));now=datetime.now(KST)
        rows=[Event(f'{kind}:1:{i}',1,'검사 과목',kind,f'검사 일정 {i}',(now+timedelta(days=i%20+1)).isoformat(),False) for kind in ('assignment','movie') for i in range(min(10000,max(1,count)))]
        window.snapshot=Snapshot(rows,[Course(1,'검사 과목')]);window._reload_course_filter();window.refresh()
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self.timeout)
        QTimer.singleShot(150,self.next)

    def next(self):
        try:page=next(self.pages)
        except StopIteration:self.finish();return
        w=self.window
        target=w.assignment_list.viewport() if page==2 else w.video_list.viewport() if page==1 else w.tabs.widget(page)
        self.active=dict(page=page,started=time.perf_counter(),target=target,painted=False)
        target.installEventFilter(self);self.timer.start(4000)
        QTest.mouseClick(w.nav[page],Qt.MouseButton.LeftButton)
        self.active['handler_ms']=(time.perf_counter()-self.active['started'])*1000
        target.update()

    def eventFilter(self,watched,event):
        sample=self.active
        if sample and watched is sample['target'] and event.type()==QEvent.Type.Paint and not sample['painted']:
            sample['painted']=True
            # Runs after paintEvent returns, including its native text rendering.
            QTimer.singleShot(0,self.painted)
        return False

    def painted(self):
        if not self.active:return
        sample=self.active;elapsed=(time.perf_counter()-sample['started'])*1000
        sample['target'].removeEventFilter(self);self.timer.stop();self.active=None
        self.samples.append(dict(page=sample['page'],click_to_paint_ms=round(elapsed,2),handler_ms=round(sample['handler_ms'],2),selected=self.window.tabs.currentIndex()))
        QTimer.singleShot(180,self.next)

    def timeout(self):
        self.samples.append(dict(page=self.active['page'],error='paint timeout'));self.finish()

    def finish(self):
        result=dict(items=len(self.window.snapshot.events),samples=self.samples,passed=bool(self.samples) and all('error' not in s and s['click_to_paint_ms']<1000 and s['page']==s['selected'] for s in self.samples))
        self.output.parent.mkdir(parents=True,exist_ok=True);self.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
        self.window.dispose();QApplication.instance().exit(0 if result['passed'] else 1)
