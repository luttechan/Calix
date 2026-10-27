"""Cursor-anchored native property editor for synchronized and personal events."""
import sqlite3
from PySide6.QtCore import Qt,QTimer,QPoint,Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFrame,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPlainTextEdit,QComboBox,QPushButton,QToolButton,QScrollArea
from .event_view import EVENT_ROLE
from .event_choices import EventChoices
from .design import icon,colors


def label(value='',name='muted'):
    widget=QLabel(value);widget.setObjectName(name);widget.setTextFormat(Qt.TextFormat.PlainText);return widget


def popup_position(point,size,area):
    x=point.x()+14;y=point.y()+18
    if x+size.width()>area.right()-8:x=point.x()-size.width()-12
    if y+size.height()>area.bottom()-8:y=point.y()-size.height()-12
    return QPoint(max(area.left()+8,min(x,area.right()-size.width()-7)),max(area.top()+8,min(y,area.bottom()-size.height()-7)))


class EventPopover(QFrame):
    original_requested=Signal(object)
    advanced_requested=Signal(object)
    def __init__(self,day,events,types,save,parent=None,read_only=False):
        super().__init__(parent,Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint);self.setObjectName('eventPopover');self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose);self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose,False)
        self.rows=list(events);self.save_callback=save;self.current=None;self.loading=False;self.dirty=False;self.read_only=read_only
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(650);self.timer.timeout.connect(self.flush)
        c=colors();self.setStyleSheet(f'QFrame#eventPopover {{background:{c["surface"]};border:1px solid {c["line"]};border-radius:18px;}}')
        outer=QVBoxLayout(self);outer.setContentsMargins(18,16,18,16);outer.setSpacing(12);header=QHBoxLayout();header.addWidget(label(f'{day.month}월 {day.day}일','section'));self.count=label(f'{len(self.rows)}개 일정','badge');header.addWidget(self.count);header.addStretch()
        close=QToolButton();close.setObjectName('zoomButton');close.setIcon(icon('close'));close.setFixedSize(30,30);close.setToolTip('닫기');close.setAccessibleName('일정 상세 닫기');close.clicked.connect(self.close);header.addWidget(close);outer.addLayout(header)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.Shape.NoFrame);body=QWidget();scroll.setWidget(body);body.setAutoFillBackground(False);form=QVBoxLayout(body);form.setContentsMargins(0,0,6,0);form.setSpacing(10)
        self.chooser=QWidget();choose=QVBoxLayout(self.chooser);choose.setContentsMargins(0,0,0,0);choose.setSpacing(7)
        filters=QHBoxLayout();self.course_filter=QComboBox();self.course_filter.setAccessibleName('상세 일정 강의 선택');self.course_filter.addItem('모든 강의',None)
        for cid,name in dict((e.course_id,e.course_name) for e in self.rows).items():self.course_filter.addItem(name,cid)
        self.kind_filter=QComboBox();self.kind_filter.setAccessibleName('상세 일정 유형 선택');self.kind_filter.addItem('모든 유형',None)
        kinds={}
        for row in self.rows:kinds[self._type_key(row)]=row.type_label
        for key,name in kinds.items():self.kind_filter.addItem(name,key)
        filters.addWidget(self.course_filter,3);filters.addWidget(self.kind_filter,2);choose.addLayout(filters)
        self.query=QLineEdit();self.query.setPlaceholderText('할 일 이름 검색');self.query.setAccessibleName('상세 일정 이름 검색');self.query.setClearButtonEnabled(True);choose.addWidget(self.query)
        self.list=EventChoices();self.list.setMinimumHeight(115);self.list.setMaximumHeight(180);self.list.set_events(self.rows);self.list.selectionModel().currentChanged.connect(self._select);choose.addWidget(self.list)
        self.empty=label('일치하는 일정이 없습니다.');self.empty.hide();choose.addWidget(self.empty);self.chooser.setVisible(len(self.rows)>1);form.addWidget(self.chooser)
        self.editor=QWidget();form.addWidget(self.editor);form=QVBoxLayout(self.editor);form.setContentsMargins(0,0,0,0);form.setSpacing(10)
        self.context=label();self.context.setWordWrap(True);form.addWidget(self.context)
        form.addWidget(label('이름','fieldLabel'));self.title=QLineEdit();self.title.setMaxLength(200);self.title.setAccessibleName('일정 이름');form.addWidget(self.title)
        form.addWidget(label('유형','fieldLabel'));self.type=QComboBox();self.type.setAccessibleName('일정 유형');form.addWidget(self.type)
        form.addWidget(label('메모','fieldLabel'));self.note=QPlainTextEdit();self.note.setPlaceholderText('기억할 내용을 남기세요.');self.note.setAccessibleName('일정 메모');self.note.setMinimumHeight(95);self.note.setMaximumHeight(140);form.addWidget(self.note)
        self.source=label();self.source.setWordWrap(True);form.addWidget(self.source);form.addStretch();outer.addWidget(scroll,1)
        self.status=label('동기화 후에도 유지됩니다.');self.status.setWordWrap(True);outer.addWidget(self.status)
        actions=QHBoxLayout();self.original=QPushButton('원본 열기');self.original.clicked.connect(self.request_original);actions.addWidget(self.original)
        self.advanced=QPushButton('날짜와 반복 편집');self.advanced.clicked.connect(self.request_advanced);actions.addWidget(self.advanced);actions.addStretch();self.save_button=QPushButton('저장');self.save_button.setObjectName('primary');self.save_button.clicked.connect(self.flush);actions.addWidget(self.save_button);outer.addLayout(actions)
        self.types=types;self.title.textEdited.connect(self.changed);self.type.currentIndexChanged.connect(self.changed);self.note.textChanged.connect(self.changed)
        self.course_filter.currentIndexChanged.connect(self.filter_choices);self.kind_filter.currentIndexChanged.connect(self.filter_choices)
        self.filter_timer=QTimer(self);self.filter_timer.setSingleShot(True);self.filter_timer.setInterval(120);self.filter_timer.timeout.connect(self.filter_choices);self.query.textChanged.connect(self.queue_filter)
        if self.rows:self.list.setCurrentIndex(self.list.model().index(0));self._select(self.list.currentIndex())
        self.resize(510 if len(self.rows)>1 else 430,740 if len(self.rows)>1 else 520)
    @staticmethod
    def _type_key(event):return f'type:{event.type_id}' if event.type_id is not None else event.kind
    def request_original(self):
        if self.current:self.original_requested.emit(self.current)
    def request_advanced(self):
        if self.current:self.advanced_requested.emit(self.current)
    def queue_filter(self,*args):self.filter_timer.start()
    def filter_choices(self,*args):
        self.filter_timer.stop()
        if self.dirty and not self.flush():return
        cid=self.course_filter.currentData();kind=self.kind_filter.currentData();query=self.query.text().strip().casefold()
        rows=[e for e in self.rows if (cid is None or e.course_id==cid) and (kind is None or self._type_key(e)==kind) and (not query or query in e.title.casefold())]
        key=self.current.key if self.current else None;self.loading=True;self.list.set_events(rows);self.loading=False
        self.empty.setVisible(not rows)
        self.editor.setVisible(bool(rows));self.save_button.setEnabled(bool(rows) and not self.read_only);self.original.setEnabled(bool(rows));self.advanced.setEnabled(bool(rows) and not self.read_only)
        self.count.setText(f'{len(rows)} / {len(self.rows)}개 일정')
        if rows:
            index=next((i for i,e in enumerate(rows) if e.key==key),0);self.list.setCurrentIndex(self.list.model().index(index,0));self._select(self.list.currentIndex())
    def _select(self,index,previous=None):
        if self.loading:return
        event=index.data(EVENT_ROLE)
        if not event or (self.current and event.key==self.current.key):return
        if self.dirty and not self.flush():
            self.loading=True
            for i,row in enumerate(self.list.event_model.rows):
                if row.key==self.current.key:self.list.setCurrentIndex(self.list.model().index(i));break
            self.loading=False;return
        self.loading=True;self.current=event;self.title.setText(event.title);self.note.setPlainText(event.note);self.type.clear()
        if not event.manual:self.type.addItem('과제 (기본)' if event.kind=='assignment' else '영상 (기본)',None)
        for row in self.types:self.type.addItem(icon('custom',row['color']),row['name'],row['id'])
        self.type.setCurrentIndex(max(0,self.type.findData(event.type_id)))
        self.context.setText(event.course_name+'\n'+(event.due.strftime('%Y.%m.%d %H:%M') if event.due else '기한 없음')+' / '+event.status())
        self.source.setText('학교 이름: '+(event.source_title or event.title) if not event.manual else '개인 일정')
        self.source.setVisible(not event.manual and bool(event.source_title) and event.source_title!=event.title)
        self.original.setVisible(bool(event.url));self.advanced.setVisible(event.manual);self.advanced.setEnabled(not self.read_only)
        for widget in (self.title,self.type,self.note,self.save_button):widget.setEnabled(not self.read_only)
        self.loading=False;self.dirty=False
    def changed(self,*args):
        if self.loading or self.read_only:return
        self.dirty=True;self.status.setText('수정 중');self.timer.start()
    def flush(self):
        self.timer.stop()
        if not self.dirty or not self.current:return True
        title=self.title.text().strip()
        if not title:self.status.setText('이름을 입력하세요.');return False
        try:updated=self.save_callback(self.current,title,self.type.currentData(),self.note.toPlainText())
        except (ValueError,OSError,sqlite3.Error) as exc:self.status.setText(str(exc) if isinstance(exc,ValueError) else '저장하지 못했습니다. 다시 시도하세요.');return False
        if updated is not None:
            self.current=updated;self.rows=[updated if row.key==updated.key else row for row in self.rows];self.list.update_event(updated)
            self.source.setText('학교 이름: '+updated.source_title);self.source.setVisible(not updated.manual and bool(updated.source_title) and updated.source_title!=updated.title)
            key=self._type_key(updated)
            if self.kind_filter.findData(key)<0:self.kind_filter.addItem(updated.type_label,key)
        self.dirty=False;self.status.setText('저장됨 / 동기화 후에도 유지됩니다.');return True
    def replace_event(self,event):
        self.rows=[event if row.key==event.key else row for row in self.rows];self.current=None;self.list.update_event(event)
        for i,row in enumerate(self.list.event_model.rows):
            if row.key==event.key:self._select(self.list.model().index(i));break
    def show_near(self,point):
        screen=QGuiApplication.screenAt(point) or self.screen();area=screen.availableGeometry();self.resize(min(self.width(),area.width()-16),min(self.height(),area.height()-16));self.move(popup_position(point,self.size(),area));self.show();self.raise_();self.activateWindow()
    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape:self.close();event.accept()
        else:super().keyPressEvent(event)
    def closeEvent(self,event):
        if self.dirty and not self.title.text().strip():self.title.setText(self.current.title)
        if not self.flush():event.ignore();return
        self.timer.stop();self.filter_timer.stop();event.accept()
