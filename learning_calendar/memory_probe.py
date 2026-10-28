"""Offline repeat-use measurement with temporary synthetic data only."""
import gc,json
from datetime import datetime,timedelta
from pathlib import Path
from PySide6.QtCore import QTimer,QPoint,QCoreApplication,QEvent,QObject
from PySide6.QtWidgets import QWidget,QApplication
from .diagnostics import memory_usage
from .models import Course,Event,KST

class MemoryProbe:
    def __init__(self,window,path):
        self.w=window;self.path=Path(path);self.step=0;self.samples=[];self.checkpoints=[];self.errors=[];self.base_widgets=None
        w=self.w;area=QApplication.primaryScreen().availableGeometry();w.resize(min(1600,area.width()),min(1000,area.height()))
        now=datetime.now(KST);courses=[Course(i,f'검사 과목 {i}') for i in range(1,7)];batches={}
        for i in range(500):
            cid=i%6+1;kind='assignment' if i%2 else 'movie';due=(now+timedelta(days=i%60+1)).replace(hour=23,minute=59)
            row=Event(f'{kind}:{cid}:{i+1}',cid,f'검사 과목 {cid}',kind,f'메모리 검사 일정 {i+1}',due.isoformat(),i%9==0)
            batches.setdefault((cid,kind),[]).append(row)
        w.store.apply_batch(courses,batches)
        for i in range(5):w.store.add_timetable(i+1,i,'09:00','10:30',f'검사 교수 {i+1}','A201')
        w._sessions=w.store.timetable();w.holiday_calendar.save('2026-11-02','검사용 임시공휴일');w.holiday_calendar.set_catholic(True);w.holiday_calendar.set_birthday(True);w._reload()
        w.show_diary();w.main_stack._settle();w.diary.new_entry();w.diary.title.setText('검사');w.diary.body.setPlainText('합성 데이터로 반복 사용 메모리를 검사합니다.');w.diary.flush()
        w.show_home(animate=False);QTimer.singleShot(300,self.cycle)
    def sample(self):
        value=memory_usage()
        if value:self.samples.append(value)
    def collect(self):
        self.w.main_stack._settle();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);QApplication.processEvents();gc.collect();self.sample()
    def cycle(self):
        try:
            w=self.w;w.show_home();self.sample();w.main_stack._settle();w.select_page(0);self.sample();w.main_stack._settle();w.calendar._layout_badges()
            rows=w.snapshot.events[:3];day=rows[0].due.date();w.show_calendar_details(day,rows,QPoint(350,160));self.sample();popup=w._event_popover;popup.note.setPlainText(f'반복 검사 {self.step}');popup.list.setCurrentIndex(popup.list.model().index(1));popup.close()
            from .holiday_dialog import HolidayDialog
            dialog=HolidayDialog(w.holiday_calendar,w.selected_date,w);dialog.show();QApplication.processEvents();self.sample();dialog.close();dialog.deleteLater()
            from .special_dates_dialog import SpecialDatesDialog
            special=SpecialDatesDialog(w.holiday_calendar,w);special.show();QApplication.processEvents();self.sample();special.close();special.deleteLater()
            w.select_page(1);w.select_page(2);w.select_page(3);w.show_diary();w.main_stack._settle();w.show_home();self.sample();self.collect()
            self.step+=1
            if self.step==4:
                self.base_widgets=len(w.findChildren(QWidget));self.baseline=memory_usage()
            if self.step>=4 and self.step%4==0:
                wrappers=sum(type(obj).__name__ in ('EventPopover','HolidayDialog','SpecialDatesDialog') for obj in gc.get_objects())
                self.checkpoints.append(dict(cycle=self.step,widgets=len(w.findChildren(QWidget)),objects=len(w.findChildren(QObject)),dialog_wrappers=wrappers,**memory_usage()))
            if self.step<80:QTimer.singleShot(30,self.cycle)
            else:self.finish()
        except BaseException as exc:self.errors.append(repr(exc));self.finish()
    def finish(self):
        self.collect();end=memory_usage();peak=max((x['peak_working_set_mb'] for x in self.samples),default=0)
        result=dict(target_mb=150,synthetic_events=500,cycles=self.step,resolution=[self.w.width(),self.w.height()],baseline=getattr(self,'baseline',{}),end=end,peak_working_set_mb=peak,checkpoints=self.checkpoints,errors=self.errors,widget_count_stable=self.base_widgets is not None and len(self.w.findChildren(QWidget))<=self.base_widgets+1,within_target=bool(self.samples) and peak<=150)
        self.path.write_text(json.dumps(result,indent=2),encoding='utf-8');self.w.dispose()
