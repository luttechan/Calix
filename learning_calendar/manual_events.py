"""Locally owned tasks and reusable named color categories."""
from datetime import datetime,date,time
from PySide6.QtCore import Qt,QDate,QTime,Signal
from PySide6.QtWidgets import (QDialog,QWidget,QLabel,QLineEdit,QPushButton,QVBoxLayout,QHBoxLayout,
    QComboBox,QCheckBox,QPlainTextEdit,QListWidget,QListWidgetItem)
from .models import KST
from .controls import TimeInput,DateInput,CountInput
from .timetable_view import ColorPicker,text
from .design import icon

class TypeManager(QDialog):
    changed=Signal()
    def __init__(self,store,parent=None):
        super().__init__(parent);self.store=store;self.selected_id=None;self.setWindowTitle('일정 유형');self.resize(600,480)
        layout=QVBoxLayout(self);layout.setContentsMargins(26,24,26,24);layout.setSpacing(16)
        layout.addWidget(text('나만의 일정 유형','heading'));layout.addWidget(text('이름과 색상을 직접 정하세요.'))
        body=QHBoxLayout();body.setSpacing(20);left=QVBoxLayout();self.list=QListWidget();self.list.setObjectName('typeList');self.list.setMinimumWidth(190);self.list.currentItemChanged.connect(self._select);left.addWidget(self.list,1)
        add=QPushButton('새 유형');add.clicked.connect(self._new);left.addWidget(add);body.addLayout(left,1)
        form=QVBoxLayout();form.setSpacing(12);form.addWidget(text('유형 이름','fieldLabel'));self.name=QLineEdit();self.name.setMaxLength(24);self.name.setPlaceholderText('예: 운동, 시험, 약속');form.addWidget(self.name)
        form.addWidget(text('색상','fieldLabel'));self.picker=ColorPicker();form.addWidget(self.picker);self.error=text('','formError');self.error.setWordWrap(True);form.addWidget(self.error);form.addStretch()
        save=QPushButton('유형 저장');save.setObjectName('primary');save.clicked.connect(self._save);form.addWidget(save);self.remove=QPushButton('유형 삭제');self.remove.setObjectName('danger');self.remove.clicked.connect(self._remove);form.addWidget(self.remove);body.addLayout(form,1);layout.addLayout(body,1)
        close=QPushButton('닫기');close.clicked.connect(self.accept);layout.addWidget(close,0,Qt.AlignmentFlag.AlignRight);self.reload()
    def reload(self,select=None):
        self.types=self.store.event_types();self.list.clear()
        for row in self.types:
            item=QListWidgetItem(icon('custom',row['color']),row['name']);item.setData(Qt.ItemDataRole.UserRole,row['id']);item.setSizeHint(__import__('PySide6.QtCore',fromlist=['QSize']).QSize(150,40));self.list.addItem(item)
            if row['id']==select:self.list.setCurrentItem(item)
        if self.list.currentItem() is None and self.list.count():self.list.setCurrentRow(0)
    def _select(self,item,previous=None):
        if item is None:return
        self.selected_id=item.data(Qt.ItemDataRole.UserRole);row=next(r for r in self.types if r['id']==self.selected_id)
        self.name.setText(row['name']);self.picker.set_color(row['color']);self.remove.setEnabled(not row['usage_count'] and len(self.types)>1);self.error.clear()
    def _new(self):self.selected_id=None;self.list.clearSelection();self.name.clear();self.name.setFocus();self.remove.setEnabled(False);self.error.clear()
    def _save(self):
        try:key=self.store.save_event_type(self.name.text(),self.picker.value,self.selected_id)
        except ValueError as exc:self.error.setText(str(exc));return
        self.reload(key);self.changed.emit()
    def _remove(self):
        try:self.store.remove_event_type(self.selected_id)
        except ValueError as exc:self.error.setText(str(exc));return
        self.reload();self.changed.emit()

class ManualEventDialog(QDialog):
    types_changed=Signal()
    def __init__(self,store,courses,day=None,event=None,parent=None):
        super().__init__(parent);self.store=store;self.source_event=event;self.setWindowTitle('일정 편집' if event else '일정 추가');self.resize(520,690)
        layout=QVBoxLayout(self);layout.setContentsMargins(26,24,26,24);layout.setSpacing(12)
        layout.addWidget(text('일정 편집' if event else '새로운 일정','heading'))
        layout.addWidget(text('일정명','fieldLabel'));self.title=QLineEdit(event.title if event else '');self.title.setMaxLength(200);self.title.setPlaceholderText('무엇을 할까요?');layout.addWidget(self.title)
        layout.addWidget(text('유형','fieldLabel'));types=QHBoxLayout();self.type=QComboBox();types.addWidget(self.type,1);manage=QPushButton('유형 관리');manage.clicked.connect(self.manage_types);types.addWidget(manage);layout.addLayout(types)
        layout.addWidget(text('과목','fieldLabel'));self.course=QComboBox();self.course.addItem('개인 일정',0)
        for c in courses:self.course.addItem(c.name,c.id)
        self.course.setCurrentIndex(max(0,self.course.findData(event.course_id if event else 0)));layout.addWidget(self.course)
        layout.addWidget(text('기한','fieldLabel'));due=event.due if event else None;selected=due.date() if due else day or datetime.now(KST).date()
        self.date=DateInput(QDate(selected.year,selected.month,selected.day));self.time=TimeInput(QTime(due.hour,due.minute) if due else QTime(23,59));row=QHBoxLayout();row.addWidget(self.date,2);row.addWidget(self.time,1);layout.addLayout(row)
        flags=QHBoxLayout();self.no_due=QCheckBox('기한 없음');self.completed_box=QCheckBox('완료');flags.addWidget(self.no_due);flags.addStretch();flags.addWidget(self.completed_box);layout.addLayout(flags)
        self.no_due.toggled.connect(lambda value:(self.date.setEnabled(not value),self.time.setEnabled(not value)));self.no_due.setChecked(bool(event and event.due is None));self.completed_box.setChecked(bool(event and event.completed))
        repeat_row=QHBoxLayout();self.repeat=QComboBox()
        for name,key in (('반복 안 함','none'),('매일','daily'),('매주','weekly'),('매월','monthly')):self.repeat.addItem(name,key)
        self.repeat_count=CountInput();self.repeat_count.setMaximumWidth(110);repeat_row.addWidget(self.repeat,1);repeat_row.addWidget(self.repeat_count);layout.addLayout(repeat_row)
        def repetition(*args):
            available=not self.no_due.isChecked() and event is None
            self.repeat.setEnabled(available);self.repeat_count.setEnabled(available and self.repeat.currentData()!='none')
            if self.no_due.isChecked():self.repeat.setCurrentIndex(0)
        self.repeat.currentIndexChanged.connect(repetition);self.no_due.toggled.connect(repetition);repetition()
        if event and event.series_id:layout.addWidget(text('이번 일정만 편집합니다.','muted'))
        layout.addWidget(text('메모','fieldLabel'));self.note=QPlainTextEdit(event.note if event else '');self.note.setPlaceholderText('추가로 기억할 내용');self.note.setMaximumHeight(90);layout.addWidget(self.note,1)
        self.error=text('','formError');self.error.setWordWrap(True);layout.addWidget(self.error)
        actions=QHBoxLayout();actions.addStretch();cancel=QPushButton('취소');cancel.clicked.connect(self.reject);save=QPushButton('저장');save.setObjectName('primary');save.clicked.connect(self._save);actions.addWidget(cancel);actions.addWidget(save);layout.addLayout(actions)
        self.reload_types(event.type_id if event else None)
    def reload_types(self,selected=None):
        current=selected or self.type.currentData();self.type.clear()
        for row in self.store.event_types():self.type.addItem(icon('custom',row['color']),row['name'],row['id'])
        self.type.setCurrentIndex(max(0,self.type.findData(current)))
    def manage_types(self):
        d=TypeManager(self.store,self);d.changed.connect(lambda:(self.reload_types(),self.types_changed.emit()));d.exec();d.deleteLater()
    def values(self):
        day=self.date.date().toPython();value=self.time.time();due=None if self.no_due.isChecked() else datetime.combine(day,time(value.hour(),value.minute()),KST).isoformat()
        return dict(title=self.title.text().strip(),type_id=self.type.currentData(),course_id=self.course.currentData(),due_at=due,note=self.note.toPlainText(),completed=self.completed_box.isChecked(),key=self.source_event.key if self.source_event else None)
    def _save(self):
        if not self.title.text().strip():self.error.setText('일정명을 입력하세요.');self.title.setFocus();return
        if self.type.currentData() is None:self.error.setText('유형을 선택하세요.');return
        self.accept()


