"""Bounded, cancellable collection from authenticated, rendered course pages."""
import json
import time
from PySide6.QtCore import QObject,QTimer,QUrl,Signal
from PySide6.QtWebEngineCore import QWebEnginePage,QWebEngineSettings
from .dom_videos import SNAPSHOT_SCRIPT
from .parsers import safe_url


class CoursePage(QWebEnginePage):
    def acceptNavigationRequest(self,url,navigation_type,is_main_frame):
        return bool(safe_url(url.toString()))


class ScreenCollector(QObject):
    finished=Signal(object)
    progress=Signal(str)
    def __init__(self,profile,owner,courses,parent=None):
        super().__init__(parent);self.owner=owner;self.courses=courses;self.index=-1
        self.results=[];self.active=True;self.generation=0;self.waiting=False;self.last=None;self.stable=0;self.last_state='loading'
        self.page=CoursePage(profile,self)
        self.page.settings().setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture,True)
        self.timer=QTimer(self);self.timer.setInterval(200);self.timer.timeout.connect(self.tick)

    def start(self):self.next_course()

    def next_course(self):
        self.generation+=1;self.waiting=False;self.last=None;self.stable=0;self.last_state='loading';self.index+=1
        if self.index>=len(self.courses):
            result={'owner':self.owner,'courses':self.courses,'results':self.results}
            self.cancel();self.finished.emit(result);return
        course=self.courses[self.index];self.progress.emit(f"{course['name']} / 주차학습 화면 읽는 중")
        self.deadline=time.monotonic()+15;self.routes=set()
        self.page.setUrl(QUrl(f"https://canvas.bufs.ac.kr/courses/{int(course['id'])}"));self.timer.start()

    def tick(self):
        if not self.active:return
        if time.monotonic()>self.deadline:
            self.results.append({'course_id':self.courses[self.index]['id'],'error':'주차학습 화면을 확인하지 못했습니다.','stage':self.last_state,'path':self.page.url().path()})
            self.next_course();return
        if self.waiting:return
        self.waiting=True;generation=self.generation
        self.page.runJavaScript(SNAPSHOT_SCRIPT,lambda value:self.observed(generation,value))

    def observed(self,generation,value):
        if not self.active or generation!=self.generation:return
        self.waiting=False
        if isinstance(value,str):
            try:value=json.loads(value)
            except ValueError:return
        if not isinstance(value,dict):return
        self.last_state=str(value.get('state','loading'))
        course=self.courses[self.index]
        if value.get('state')=='navigate':
            url=safe_url(value.get('url'))
            if url and url not in self.routes and QUrl(url).path().startswith(f"/courses/{int(course['id'])}/"):
                self.routes.add(url);self.page.setUrl(QUrl(url))
            return
        if value.get('state')!='ready' or str(value.get('course_id'))!=str(course['id']):return
        if str(value.get('owner'))!=str(self.owner):return
        if not isinstance(value.get('items'),list) or len(value['items'])>10000:return
        signature=json.dumps(value,sort_keys=True,ensure_ascii=False)
        if len(signature)>2*1024*1024:return
        self.stable=self.stable+1 if signature==self.last else 0;self.last=signature
        if self.stable<2:return
        self.results.append({'course_id':course['id'],'snapshot':value});self.next_course()

    def cancel(self):
        self.active=False;self.generation+=1;self.timer.stop()
        if self.page:
            self.page.triggerAction(QWebEnginePage.WebAction.Stop);self.page.deleteLater();self.page=None
