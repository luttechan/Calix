"""Five fixed native rows with a complete schedule model."""
from PySide6.QtCore import Qt,Signal,QModelIndex
from PySide6.QtWidgets import QFrame,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QCheckBox,QSizePolicy
from .event_table import ScheduleModel
from .design import colors,category_colors,type_tokens
from .text_safety import tooltip_text

class PreviewLabel(QLabel):
    def __init__(self):super().__init__();self.full_text=''
    def setText(self,value):
        self.full_text=str(value)
        if self.isVisible():self._fit()
        else:super().setText(self.full_text)
    def _fit(self):
        super().setText(self.fontMetrics().elidedText(self.full_text,Qt.TextElideMode.ElideRight,max(1,self.contentsRect().width())))
    def resizeEvent(self,event):super().resizeEvent(event);self._fit()
    def showEvent(self,event):super().showEvent(event);self._fit()

class SchedulePreview(QFrame):
    activated=Signal(QModelIndex)
    completion_requested=Signal(object,bool)
    def __init__(self,parent=None):
        super().__init__(parent);self.setObjectName('schedulePreview');self.event_model=ScheduleModel(self);self.setAccessibleName('남은 일정');self.setMinimumHeight(170)
        outer=QVBoxLayout(self);outer.setContentsMargins(8,5,8,8);outer.setSpacing(0)
        header=QWidget();head=QHBoxLayout(header);head.setContentsMargins(10,8,10,8);head.setSpacing(8)
        for name,stretch in zip(ScheduleModel.HEADERS,(2,2,4,2,2)):head.addWidget(self.text_label(name,'muted'),stretch)
        outer.addWidget(header);self.rows=[]
        for index in range(5):
            row=QPushButton();row.setObjectName('schedulePreviewRow');row.setFixedHeight(46);row.setCursor(Qt.CursorShape.PointingHandCursor)
            box=QHBoxLayout(row);box.setContentsMargins(10,0,10,0);box.setSpacing(8)
            first=QWidget();type_box=QHBoxLayout(first);type_box.setContentsMargins(0,0,0,0);type_box.setSpacing(3)
            check=QCheckBox();check.setAccessibleName('일정 완료');check.setFixedWidth(20);type_box.addWidget(check)
            type_label=self.text_label('');type_label.setSizePolicy(QSizePolicy.Policy.Maximum,QSizePolicy.Policy.Fixed);type_label.setMaximumWidth(104);type_label.setFixedHeight(24);type_box.addWidget(type_label,0,Qt.AlignmentFlag.AlignVCenter);type_box.addStretch();box.addWidget(first,2);fields=[type_label]
            for stretch in (2,4,2,2):
                label=self.text_label('');box.addWidget(label,stretch);fields.append(label)
            row.clicked.connect(lambda checked=False,n=index:self.open_row(n));check.clicked.connect(lambda checked,n=index:self.complete_row(n,checked))
            self.rows.append((row,fields,check));outer.addWidget(row);row.hide()
        self.empty_label=self.text_label('남은 일정이 없습니다','muted');self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter);outer.addWidget(self.empty_label,1);outer.addStretch()
    @staticmethod
    def text_label(text,name=''):
        label=PreviewLabel();label.setObjectName(name);label.setTextFormat(Qt.TextFormat.PlainText);label.setMinimumWidth(0);label.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred);label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents);label.setText(text);return label
    def set_events(self,rows,now=None):
        self.event_model.set_events(rows,now);events=self.event_model.rows
        for n,(row,fields,check) in enumerate(self.rows):
            row.setVisible(n<len(events))
            if n>=len(events):continue
            event=events[n];values=[str(self.event_model.data(self.event_model.index(n,column)) or '') for column in range(5)]
            for label,value in zip(fields,values):label.setText(value);label.setToolTip(tooltip_text(value))
            from .models import deadline_display
            status_style='color:#D94B61;' if deadline_display(event,self.event_model.now)[1]=='red' else ''
            if fields[4].styleSheet()!=status_style:fields[4].setStyleSheet(status_style)
            palette=category_colors();kind='assignment' if event.kind=='assignment' else 'movie';tokens=type_tokens(event.type_color) if event.type_id is not None else {key:palette[kind+'_'+key] for key in ('ink','bg','line')}
            style=f'color:{tokens["ink"]};background:{tokens["bg"]};border:1px solid {tokens["line"]};border-radius:5px;padding:2px 7px;font-size:12px;'
            if fields[0].styleSheet()!=style:fields[0].setStyleSheet(style)
            row.setAccessibleName(' / '.join(values));check.blockSignals(True);check.setChecked(event.completed);check.setVisible(event.manual);check.blockSignals(False)
        self.empty_label.setVisible(not events)
    def open_row(self,row):
        if row<len(self.event_model.rows):self.activated.emit(self.event_model.index(row,0))
    def complete_row(self,row,checked):
        if row<len(self.event_model.rows):self.completion_requested.emit(self.event_model.rows[row],checked)
    def viewport(self):return self
