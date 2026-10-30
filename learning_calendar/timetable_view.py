"""Minute-accurate native weekly board. Paint shapes; leave all text to Qt."""
from datetime import datetime,timedelta
from PySide6.QtCore import Qt,QTimer,QTime,Signal,QPoint,QRectF
from PySide6.QtGui import QColor,QPainter,QPen
from PySide6.QtWidgets import (QWidget,QFrame,QLabel,QPushButton,QLineEdit,QVBoxLayout,QHBoxLayout,
    QGridLayout,QScrollArea,QSizePolicy,QDialog,QComboBox,QTimeEdit,QAbstractSpinBox,QMenu,QApplication,QCheckBox,QDialogButtonBox,QLayout,QBoxLayout)
from .models import KST
from .design import colors
from .schedule_colors import PALETTE,course_color,normalize_color,minutes,clock
from .controls import TimeInput,CheckToggle as QCheckBox
from .text_safety import tooltip_text

DAYS=('월','화','수','목','금','토','일')

def text(value,name='muted',parent=None):
    label=QLabel(value,parent);label.setObjectName(name);label.setTextFormat(Qt.TextFormat.PlainText);return label

class ElidedText(QLabel):
    def __init__(self,value='',parent=None):
        super().__init__(parent);self.full='';self.setMinimumWidth(0);self.setTextFormat(Qt.TextFormat.PlainText);self.set_value(value)
    def set_value(self,value):
        self.full=str(value);self.setToolTip(tooltip_text(self.full))
        if self.isVisible():self._fit()
        else:super().setText(self.full)
    def _fit(self):super().setText(self.fontMetrics().elidedText(self.full,Qt.TextElideMode.ElideRight,max(1,self.width())))
    def resizeEvent(self,event):super().resizeEvent(event);self._fit()
    def showEvent(self,event):super().showEvent(event);self._fit()

class ColorPicker(QWidget):
    changed=Signal(str)
    def __init__(self,parent=None,columns=4):
        super().__init__(parent);self.value=PALETTE[0][0];self.buttons={}
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(10)
        grid=QGridLayout();grid.setSpacing(8)
        for i,(value,name) in enumerate(PALETTE):
            b=QPushButton();b.setObjectName('colorSwatch');b.setFixedSize(32,32);b.setCheckable(True);b.setAutoExclusive(True)
            b.setAccessibleName(name);b.setToolTip(name);b.clicked.connect(lambda checked=False,v=value:self.choose(v))
            grid.addWidget(b,i//columns,i%columns);self.buttons[value]=b
        layout.addLayout(grid)
        self.hex=QLineEdit();self.hex.setObjectName('colorHex');self.hex.setPlaceholderText('#7582E6');self.hex.setMaxLength(7)
        self.hex.setAccessibleName('사용자 지정 색상');self.hex.editingFinished.connect(self._custom);layout.addWidget(self.hex)
        self.set_color(self.value)
    def set_color(self,value):
        self.value=normalize_color(value) or PALETTE[0][0];self.hex.setText(self.value)
        for color,b in self.buttons.items():
            selected=color==self.value;b.setChecked(selected);b.setText('✓' if selected else '')
            b.setStyleSheet(f'QPushButton {{background:{color};color:#FFFFFF;border:2px solid {colors()["ink"] if selected else color};border-radius:10px;padding:0;}}')
    def choose(self,value):self.set_color(value);self.changed.emit(self.value)
    def _custom(self):
        try:self.choose(self.hex.text())
        except ValueError:self.hex.setText(self.value)

class SessionEditor(QDialog):
    def __init__(self,courses,item=None,parent=None):
        super().__init__(parent);self.setWindowTitle('수업 편집' if item else '수업 추가');self.resize(460,610)
        layout=QVBoxLayout(self);layout.setContentsMargins(28,26,28,24);layout.setSpacing(12)
        layout.addWidget(text('수업 편집' if item else '새로운 수업','heading'));layout.addWidget(text('시간과 색상을 내 리듬에 맞춰요.'))
        layout.addWidget(text('과목','fieldLabel'));self.course=QComboBox()
        for c in courses:self.course.addItem(c.name,c.id)
        layout.addWidget(self.course)
        layout.addWidget(text('요일','fieldLabel'));days=QHBoxLayout();days.setSpacing(6);self.days=[]
        for i,day in enumerate(DAYS):
            b=QPushButton(day);b.setObjectName('dayChoice');b.setCheckable(True);b.setAutoExclusive(True);b.setMinimumWidth(38)
            days.addWidget(b);self.days.append(b)
        self.days[0].setChecked(True);layout.addLayout(days)
        times=QHBoxLayout();times.setSpacing(12)
        self.start=TimeInput(QTime(9,0));self.end=TimeInput(QTime(10,30))
        for title,field in (('시작',self.start),('종료',self.end)):
            column=QVBoxLayout();column.setSpacing(7);column.addWidget(text(title,'fieldLabel'));field.setDisplayFormat('HH:mm');field.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons);column.addWidget(field);times.addLayout(column)
        layout.addLayout(times)
        details=QHBoxLayout();self.prof=QLineEdit();self.room=QLineEdit()
        for title,field,placeholder in (('교수',self.prof,'선택 입력'),('강의실',self.room,'예: A201')):
            column=QVBoxLayout();column.setSpacing(7);column.addWidget(text(title,'fieldLabel'));field.setPlaceholderText(placeholder);column.addWidget(field);details.addLayout(column)
        layout.addLayout(details);layout.addWidget(text('수업 색상','fieldLabel'));self.color_picker=ColorPicker(columns=8);layout.addWidget(self.color_picker)
        self.error=text('','formError');self.error.setWordWrap(True);layout.addWidget(self.error);layout.addStretch()
        actions=QHBoxLayout();cancel=QPushButton('취소');cancel.clicked.connect(self.reject);save=QPushButton('저장');save.setObjectName('primary');save.clicked.connect(self._save)
        actions.addStretch();actions.addWidget(cancel);actions.addWidget(save);layout.addLayout(actions)
        if item:
            self.course.setCurrentIndex(self.course.findData(item['course_id']));self.days[item['day']].setChecked(True)
            if self.course.currentIndex()<0:self.error.setText('기존 과목을 찾을 수 없습니다. 과목을 선택하세요.')
            self.start.setTime(QTime.fromString(item['start_time'],'HH:mm'));self.end.setTime(QTime.fromString(item['end_time'],'HH:mm'))
            self.prof.setText(item.get('professor',''));self.room.setText(item.get('room',''))
        self.color_picker.set_color((item or {}).get('color') or course_color(self.course.currentData() or 0))
        self.course.currentIndexChanged.connect(lambda *_:self.color_picker.set_color(course_color(self.course.currentData() or 0)))
    def _save(self):
        if self.course.currentData() is None:self.error.setText('과목을 선택하세요.');return
        if not self.start.time().isValid() or not self.end.time().isValid():self.error.setText('시간을 00:00~23:59로 입력하세요.');return
        if self.start.time()>=self.end.time():self.error.setText('종료는 시작보다 늦어야 합니다.');return
        validator=getattr(self,'validation',None)
        error=validator(self.values()) if validator else ''
        if error:self.error.setText(error);return
        self.accept()
    def values(self):
        return (self.course.currentData(),next(i for i,b in enumerate(self.days) if b.isChecked()),self.start.time().toString('HH:mm'),self.end.time().toString('HH:mm'),self.prof.text().strip(),self.room.text().strip())
    @property
    def color_value(self):return self.color_picker.value

class SessionBlock(QFrame):
    selected=Signal(int);edit=Signal(int);moved=Signal(int,int,str,str)
    def __init__(self,surface):
        super().__init__(surface);self.surface=surface;self.row={};self._drag=False;self._press=None
        self.setObjectName('classBlock');self.setFocusPolicy(Qt.FocusPolicy.StrongFocus);self.setCursor(Qt.CursorShape.OpenHandCursor)
        layout=QVBoxLayout(self);self.body_layout=layout;layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint);layout.setContentsMargins(11,9,9,8);layout.setSpacing(3)
        self.title=ElidedText();self.title.setObjectName('classTitle');self.time=text('','classTime');self.room=ElidedText();self.room.setObjectName('classRoom')
        for label in (self.title,self.time,self.room):label.setMinimumWidth(0);label.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        for label in (self.title,self.time,self.room):label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents);layout.addWidget(label)
        self.counts=QWidget();self.counts.setMinimumWidth(0);self.counts.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred);self.counts.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents);pills=QHBoxLayout(self.counts);self.pills=pills;pills.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint);pills.setContentsMargins(0,0,0,0);pills.setSpacing(4)
        self.assignments=text('','assignmentBadge');self.videos=text('','movieBadge')
        for pill in (self.assignments,self.videos):pill.setMinimumWidth(0);pill.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred);pill.setStyleSheet('padding:2px 4px;font-size:11px;');pills.addWidget(pill)
        layout.addWidget(self.counts)
        layout.addStretch()
    def configure(self,row,name,selected=False,workload=(0,0)):
        self.row=row;self.title.set_value(name);self.time.setText(row['start_time']+' – '+row['end_time']);self.room.set_value(' / '.join(filter(None,(row.get('professor',''),row.get('room','')))))
        self.assignments.setText(f'과제 {workload[0]}');self.videos.setText(f'영상 {workload[1]}')
        self.setAccessibleName(f'{name} / {DAYS[row["day"]]} / {self.time.text()} / {self.room.full} / 남은 과제 {workload[0]}건 / 남은 영상 {workload[1]}건');self.setToolTip(tooltip_text(self.accessibleName()))
        color=row.get('color') or course_color(row['course_id']);accent=QColor(color);base=QColor(colors()['surface'])
        dark=base.lightness()<128;mix=.21 if dark else .13
        bg=QColor(*[round(accent.getRgb()[i]*mix+base.getRgb()[i]*(1-mix)) for i in range(3)]).name()
        edge=QColor('#8B9CBB') if dark and accent.lightness()<55 else accent.darker(190) if not dark and accent.lightness()>215 else accent
        self.setStyleSheet(f'QFrame#classBlock {{background:{bg};border:{2 if selected else 1}px solid {edge.name()};border-left:4px solid {edge.name()};border-radius:12px;}}')
        self.fit_content()
    def resizeEvent(self,event):
        super().resizeEvent(event);self.fit_content()
    def fit_content(self):
        if not hasattr(self,'body_layout'):return
        height=self.height()
        self.body_layout.setContentsMargins(6,2,4,2) if height<42 else self.body_layout.setContentsMargins(11,9,9,8)
        narrow=self.width()<140
        if self.row:self.time.setText(self.row['start_time']+('\n' if narrow else ' – ')+self.row['end_time'])
        stacked=self.width()<116
        self.time.setFixedHeight(32 if narrow else 18);self.pills.setDirection(QBoxLayout.Direction.TopToBottom if stacked else QBoxLayout.Direction.LeftToRight)
        self.title.setVisible(height>=22);self.time.setVisible(height>=65 if narrow else height>=57);self.room.setVisible(height>=140 if narrow else height>=76);self.counts.setVisible(height>=110 if stacked else height>=100 if narrow else height>=112)
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:self.selected.emit(self.row['id']);self._press=event.globalPosition().toPoint();self._offset=event.position().toPoint();self._drag=False
        super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self.surface.interactive and self._press is not None and event.buttons()&Qt.MouseButton.LeftButton:
            if (event.globalPosition().toPoint()-self._press).manhattanLength()>=QApplication.startDragDistance():self._drag=True
            if self._drag:self.raise_();self.move(self.surface.mapFromGlobal(event.globalPosition().toPoint())-self._offset)
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        if self._drag:
            day,start=self.surface.slot_at(self.pos()+QPoint(4,0));duration=minutes(self.row['end_time'])-minutes(self.row['start_time'])
            start=max(0,min(start,1439-duration))
            if day not in self.surface.off_days:self.moved.emit(self.row['id'],day,clock(start),clock(start+duration))
            else:self.surface.relayout()
        self._press=None;self._drag=False;super().mouseReleaseEvent(event)
    def mouseDoubleClickEvent(self,event):
        # A class is not an empty slot. Never forward its double click to the
        # weekly surface, including after the modal editor has been dismissed.
        event.accept();self._press=None;self._drag=False
        if event.button()==Qt.MouseButton.LeftButton and self.surface.interactive:self.edit.emit(self.row['id'])
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):self.edit.emit(self.row['id'])
        else:super().keyPressEvent(event)

class WeekSurface(QWidget):
    selected=Signal(int);edit=Signal(int);create=Signal(int,str);moved=Signal(int,int,str,str)
    AXIS=52;TOP=12
    def __init__(self,parent=None):
        super().__init__(parent);self.setObjectName('weekSurface');self.rows=[];self.names={};self.blocks={};self.time_labels={};self.days=5;self.hour_height=76;self.start=8*60;self.end=20*60;self.selected_id=None;self.interactive=True;self.off_days=set();self.off_labels={}
    def set_data(self,rows,names,workloads=None):
        self.rows=list(rows);self.names=names;self.workloads=workloads or {}
        self.start=min([8*60]+[(minutes(r['start_time'])//60)*60 for r in rows]);self.end=max([19*60]+[((minutes(r['end_time'])+59)//60)*60 for r in rows])
        live={r['id'] for r in rows}
        for key in list(self.blocks):
            if key not in live:self.blocks.pop(key).deleteLater()
        for row in rows:
            if row['id'] not in self.blocks:
                card=SessionBlock(self);card.selected.connect(self.selected);card.edit.connect(self.edit);card.moved.connect(self.moved);self.blocks[row['id']]=card
            self.blocks[row['id']].configure(row,names.get(row['course_id'],'수업'),self.selected_id==row['id'],self.workloads.get(row['course_id'],(0,0)))
        self.relayout()
    def relayout(self):
        self.setMinimumHeight(round((self.end-self.start)/60*self.hour_height+28))
        width=(self.width()-self.AXIS)/self.days
        for row in self.rows:
            block=self.blocks[row['id']];block.setVisible(row['day']<self.days and row['day'] not in self.off_days)
            y=self.TOP+(minutes(row['start_time'])-self.start)*self.hour_height/60
            height=(minutes(row['end_time'])-minutes(row['start_time']))*self.hour_height/60
            block.setGeometry(round(self.AXIS+row['day']*width+5),round(y)+1,max(24,round(width)-10),max(3,round(height)-2))
        hours=set(range(self.start//60,self.end//60+1))
        for hour in list(self.time_labels):
            if hour not in hours:self.time_labels.pop(hour).deleteLater()
        for hour in hours:
            if hour not in self.time_labels:self.time_labels[hour]=text(f'{hour:02d}:00','timeAxis',self)
            self.time_labels[hour].setGeometry(0,round(self.TOP+(hour*60-self.start)*self.hour_height/60)-8,44,18);self.time_labels[hour].show()
        for day in range(7):
            if day not in self.off_labels:
                self.off_labels[day]=text('공강','section',self);self.off_labels[day].setAlignment(Qt.AlignmentFlag.AlignCenter);self.off_labels[day].setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self.off_labels[day].setVisible(day<self.days and day in self.off_days)
            self.off_labels[day].setGeometry(round(self.AXIS+day*width+8),self.TOP+35,max(1,round(width)-16),44)
        self.update()
    def resizeEvent(self,event):super().resizeEvent(event);self.relayout()
    def slot_at(self,point):
        width=max(1,(self.width()-self.AXIS)/self.days);day=max(0,min(self.days-1,int((point.x()-self.AXIS)/width)))
        start=round(((point.y()-self.TOP)*60/self.hour_height+self.start)/15)*15
        return day,max(0,min(start,1380))
    def mouseDoubleClickEvent(self,event):
        event.accept()
        if not self.interactive or event.button()!=Qt.MouseButton.LeftButton:return
        if event.position().x()<self.AXIS or event.position().y()<self.TOP:return
        if any(card.isVisible() and card.geometry().contains(event.position().toPoint()) for card in self.blocks.values()):return
        day,start=self.slot_at(event.position().toPoint())
        if day not in self.off_days:self.create.emit(day,clock(start))
    def paintEvent(self,event):
        c=colors();p=QPainter(self);p.fillRect(self.rect(),QColor(c['surface']));width=(self.width()-self.AXIS)/self.days;now=datetime.now(KST)
        if now.weekday()<self.days:
            shade=QColor(c['soft']);shade.setAlpha(110);p.fillRect(QRectF(self.AXIS+now.weekday()*width,0,width,self.height()),shade)
        p.setPen(QPen(QColor(c['line']),1))
        for day in range(self.days+1):p.drawLine(round(self.AXIS+day*width),0,round(self.AXIS+day*width),self.height())
        for hour in range(self.start//60,self.end//60+1):
            y=round(self.TOP+(hour*60-self.start)*self.hour_height/60);p.drawLine(self.AXIS,y,self.width(),y)
        if now.weekday()<self.days and self.start<now.hour*60+now.minute<self.end:
            y=self.TOP+(now.hour*60+now.minute-self.start)*self.hour_height/60;p.setPen(QPen(QColor(c['accent']),1.5));p.drawLine(round(self.AXIS+now.weekday()*width),round(y),round(self.AXIS+(now.weekday()+1)*width),round(y))
        p.end()

class TimetableView(QWidget):
    add_requested=Signal();edit_requested=Signal(int);remove_requested=Signal(int);color_changed=Signal(int,str);move_requested=Signal(int,int,str,str);slot_requested=Signal(int,str)
    off_days_changed=Signal(object)
    def __init__(self,parent=None):
        super().__init__(parent);self.rows=[];self.names={};self.workloads={};self.selected_id=None;self._setting_color=False;self.read_only=False
        outer=QVBoxLayout(self);outer.setContentsMargins(0,0,0,0);outer.setSpacing(16)
        top=QHBoxLayout();head=QVBoxLayout();head.setSpacing(4);self.summary=text('등록된 수업 없음');head.addWidget(self.summary);top.addLayout(head,1)
        self.weekdays=QPushButton('주중');self.weekdays.setObjectName('segment');self.weekdays.setCheckable(True);self.weekdays.setChecked(True)
        self.all_days=QPushButton('주간');self.all_days.setObjectName('segment');self.all_days.setCheckable(True)
        self.weekdays.clicked.connect(lambda:self.set_days(5));self.all_days.clicked.connect(lambda:self.set_days(7));top.addWidget(self.weekdays);top.addWidget(self.all_days)
        self.off_button=QPushButton('공강 설정');self.off_button.clicked.connect(self.edit_off_days);top.addWidget(self.off_button)
        self.edit_button=QPushButton('수정');self.edit_button.clicked.connect(lambda:self.selected_id is not None and self.edit_requested.emit(self.selected_id));top.addWidget(self.edit_button)
        self.add_button=QPushButton('수업 추가');self.add_button.setObjectName('primary');self.add_button.clicked.connect(self.add_requested);top.addWidget(self.add_button);outer.addLayout(top)
        content=QHBoxLayout();content.setSpacing(16)
        board=QFrame();board.setObjectName('boardCard');box=QVBoxLayout(board);box.setContentsMargins(14,12,10,12);box.setSpacing(0)
        self.headers=QWidget();self.headers.setFixedHeight(44);self.day_labels=[]
        monday=datetime.now(KST).date()-timedelta(days=datetime.now(KST).weekday())
        for day in range(7):
            label=text(f'{DAYS[day]}  {(monday+timedelta(days=day)).day}','weekDay',self.headers);label.setAlignment(Qt.AlignmentFlag.AlignCenter);label.setMinimumHeight(44);self.day_labels.append(label)
        box.addWidget(self.headers)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(True);self.scroll.setFrameShape(QFrame.Shape.NoFrame);self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.surface=WeekSurface();self.scroll.setWidget(self.surface);box.addWidget(self.scroll,1)
        self.scroll.viewport().installEventFilter(self)
        self.headers.installEventFilter(self);self.surface.installEventFilter(self)
        self.align_timer=QTimer(self);self.align_timer.setSingleShot(True);self.align_timer.timeout.connect(self.align_headers)
        footer=QHBoxLayout();footer.addWidget(text('빈 시간을 두 번 눌러 추가 / 수업을 끌어 이동','caption'));footer.addStretch()
        for title,step in (('−',-12),('+',12)):
            button=QPushButton(title);button.setObjectName('zoomButton');button.setAccessibleName('시간표 축소' if step<0 else '시간표 확대');button.setToolTip(button.accessibleName());button.setFixedSize(30,30);button.clicked.connect(lambda checked=False,s=step:self.zoom(s));footer.addWidget(button)
        box.addLayout(footer);content.addWidget(board,1)
        self.inspector=QFrame();self.inspector.setObjectName('inspector');self.inspector.setFixedWidth(248);details=QVBoxLayout(self.inspector);details.setContentsMargins(20,22,20,20);details.setSpacing(14)
        details.addWidget(text('선택한 수업','eyebrow'));self.name=text('수업을 선택하세요.','section');self.name.setWordWrap(True);details.addWidget(self.name)
        self.detail_time=text('','muted');self.detail_room=text('','muted');self.detail_prof=text('','muted')
        for label in (self.detail_time,self.detail_room,self.detail_prof):label.setWordWrap(True);details.addWidget(label)
        self.remaining_assignments=text('','assignmentBadge');self.remaining_videos=text('','movieBadge')
        for pill in (self.remaining_assignments,self.remaining_videos):details.addWidget(pill)
        details.addSpacing(8);details.addWidget(text('수업 색상','fieldLabel'));self.picker=ColorPicker();self.picker.changed.connect(self._color);details.addWidget(self.picker);details.addStretch()
        self.remove_button=QPushButton('수업 삭제');self.remove_button.setObjectName('danger');self.remove_button.clicked.connect(lambda:self.selected_id is not None and self.remove_requested.emit(self.selected_id));details.addWidget(self.remove_button)
        content.addWidget(self.inspector);outer.addLayout(content,1)
        self.surface.selected.connect(self.select);self.surface.edit.connect(self.edit_requested);self.surface.create.connect(self.slot_requested);self.surface.moved.connect(self.move_requested)
        self.set_days(5);self.select(None)
        from .popup_tools import add_hints
        add_hints(self)
    def set_data(self,rows,names,workloads=None,*,off_days=()):
        self.rows=list(rows);self.names=names;self.workloads=workloads or {};self.surface.off_days=set(off_days)
        scheduled=[r for r in rows if r['day'] not in self.surface.off_days];total=sum(minutes(r['end_time'])-minutes(r['start_time']) for r in scheduled)
        now=datetime.now(KST);monday=now.date()-timedelta(days=now.weekday())
        for day,label in enumerate(self.day_labels):
            label.setText(f'{DAYS[day]}  {(monday+timedelta(days=day)).day}'+(' / 공강' if day in self.surface.off_days else ''));label.setObjectName('weekDayToday' if day==now.weekday() else 'weekDay')
            label.style().unpolish(label);label.style().polish(label)
        self.summary.setText(f'{len(scheduled)}개 수업 / 주 {total//60}시간'+(f' {total%60}분' if total%60 else ''))
        self.surface.set_data(rows,names,self.workloads)
        if self.selected_id not in {r['id'] for r in scheduled}:self.selected_id=next((r['id'] for r in scheduled),None)
        if any(r['day']>=5 for r in rows) and self.surface.days==5:self.set_days(7)
        self.select(self.selected_id);self.align_timer.start(0)
    def select(self,item_id):
        self.selected_id=item_id;self.surface.selected_id=item_id;row=next((r for r in self.rows if r['id']==item_id and r['day'] not in self.surface.off_days),None)
        editable=row is not None and not self.read_only
        self.edit_button.setEnabled(editable);self.remove_button.setEnabled(editable);self.picker.setEnabled(editable)
        if row:
            self.name.setText(self.names.get(row['course_id'],'수업'));self.detail_time.setText(f'{DAYS[row["day"]]}요일\n{row["start_time"]} – {row["end_time"]}')
            self.detail_room.setText(row.get('room') or '강의실 미지정');self.detail_prof.setText(row.get('professor') or '교수 미지정')
            assignment,movie=self.workloads.get(row['course_id'],(0,0));self.remaining_assignments.setText(f'남은 과제 {assignment}건');self.remaining_videos.setText(f'남은 영상 {movie}건')
            self._setting_color=True;self.picker.set_color(row.get('color') or course_color(row['course_id']));self._setting_color=False
        else:self.name.setText('수업을 선택하세요.');self.detail_time.clear();self.detail_room.clear();self.detail_prof.clear()
        self.remaining_assignments.setVisible(row is not None);self.remaining_videos.setVisible(row is not None)
        for item in self.rows:self.surface.blocks[item['id']].configure(item,self.names.get(item['course_id'],'수업'),item['id']==item_id,self.workloads.get(item['course_id'],(0,0)))
    def _color(self,value):
        if not self._setting_color and self.selected_id is not None:self.color_changed.emit(self.selected_id,value)
    def set_days(self,count):
        self.surface.days=count;self.weekdays.setChecked(count==5);self.all_days.setChecked(count==7)
        for i,label in enumerate(self.day_labels):label.setVisible(i<count)
        self.surface.relayout()
        self.fit_inspector()
        self.align_timer.start(0)
    def zoom(self,step):self.surface.hour_height=max(52,min(124,self.surface.hour_height+step));self.surface.relayout()
    def set_read_only(self,value):
        self.read_only=bool(value);self.surface.interactive=not value;self.add_button.setEnabled(not value);self.off_button.setEnabled(not value);self.select(self.selected_id)
    def resizeEvent(self,event):super().resizeEvent(event);self.fit_inspector()
    def fit_inspector(self):
        if hasattr(self,'inspector'):self.inspector.setVisible(self.width()>=344+self.surface.days*132)
    def eventFilter(self,obj,event):
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.Resize,QEvent.Type.Show,QEvent.Type.StyleChange) and hasattr(self,'align_timer'):self.align_timer.start(0)
        return super().eventFilter(obj,event)
    def align_headers(self):
        # These widgets are siblings. mapTo(parent, ...) requires an ancestor;
        # map through global coordinates to avoid accumulating parent offsets.
        offset=self.surface.mapToGlobal(QPoint(0,0)).x()-self.headers.mapToGlobal(QPoint(0,0)).x();width=(self.surface.width()-self.surface.AXIS)/self.surface.days
        for day,label in enumerate(self.day_labels):
            left=round(offset+self.surface.AXIS+day*width);right=round(offset+self.surface.AXIS+(day+1)*width)
            label.setGeometry(left,0,max(1,right-left),44)
    def edit_off_days(self):
        if self.read_only:return
        dialog=QDialog(self);dialog.setWindowTitle('공강 설정');layout=QVBoxLayout(dialog);boxes=[]
        for day,name in enumerate(DAYS):
            box=QCheckBox(name+'요일');box.setChecked(day in self.surface.off_days);layout.addWidget(box);boxes.append(box)
        actions=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);actions.accepted.connect(dialog.accept);actions.rejected.connect(dialog.reject);layout.addWidget(actions)
        if dialog.exec():self.off_days_changed.emit({day for day,box in enumerate(boxes) if box.isChecked()})
        dialog.deleteLater()
