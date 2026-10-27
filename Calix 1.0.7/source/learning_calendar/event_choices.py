"""Stable native table for choosing an event without resetting selection on save."""
from PySide6.QtCore import QAbstractTableModel,QModelIndex,Qt,Signal
from PySide6.QtGui import QColor,QPalette,QPen
from PySide6.QtWidgets import QTableView,QAbstractItemView,QHeaderView,QStyledItemDelegate,QStyleOptionViewItem,QStyle,QApplication
from .event_view import EVENT_ROLE
from .design import colors,type_tokens,category_colors


class ChoiceTypeDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        event=index.data(EVENT_ROLE)
        if event is None:return
        c=category_colors();prefix='assignment' if event.kind=='assignment' else 'movie'
        tokens=type_tokens(event.type_color) if event.type_id is not None else dict(ink=c[prefix+'_ink'],bg=c[prefix+'_bg'],line=c[prefix+'_line'])
        rect=option.rect.adjusted(4,7,-4,-7);painter.save();painter.setRenderHint(painter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(tokens['line']),1));painter.setBrush(QColor(tokens['bg']));painter.drawRoundedRect(rect,5,5);painter.restore()
        native=QStyleOptionViewItem(option);self.initStyleOption(native,index);native.rect=rect.adjusted(4,0,-4,0);native.state=QStyle.StateFlag.State_Enabled
        native.displayAlignment=Qt.AlignmentFlag.AlignCenter;native.palette.setColor(QPalette.ColorRole.Text,QColor(tokens['ink']))
        QApplication.style().drawControl(QStyle.ControlElement.CE_ItemViewItem,native,painter,option.widget)


class EventChoiceModel(QAbstractTableModel):
    def __init__(self,parent=None):super().__init__(parent);self.rows=[]
    def index(self,row,column=0,parent=QModelIndex()):return super().index(row,column,parent)
    def rowCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self.rows)
    def columnCount(self,parent=QModelIndex()):return 0 if parent.isValid() else 3
    def headerData(self,section,orientation,role=Qt.ItemDataRole.DisplayRole):
        if orientation==Qt.Orientation.Horizontal and role==Qt.ItemDataRole.DisplayRole:return ('강의','Type','할 일 이름')[section]
    def data(self,index,role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0<=index.row()<len(self.rows):return None
        event=self.rows[index.row()]
        if role==EVENT_ROLE:return event
        if role==Qt.ItemDataRole.UserRole:return event.key
        if role==Qt.ItemDataRole.DisplayRole:return (event.course_name,event.type_label,event.title)[index.column()]
        if role in (Qt.ItemDataRole.ToolTipRole,Qt.ItemDataRole.AccessibleTextRole):return f'{event.course_name} / {event.type_label} / {event.title}'
        if role==Qt.ItemDataRole.ForegroundRole:return QColor(type_tokens(event.type_color)['ink'] if index.column()==1 and event.type_color else colors()['ink'])
    def set_events(self,rows):
        self.beginResetModel();self.rows=list(rows);self.endResetModel()
    def update_event(self,event):
        for row,item in enumerate(self.rows):
            if item.key==event.key:
                self.rows[row]=event;self.dataChanged.emit(self.index(row,0),self.index(row,2));break


class EventChoices(QTableView):
    completion_requested=Signal(object,bool)
    def __init__(self,parent=None):
        super().__init__(parent);self.setObjectName('eventChoices');self.event_model=EventChoiceModel(self);self.setModel(self.event_model)
        self.setShowGrid(False);self.setItemDelegateForColumn(1,ChoiceTypeDelegate(self))
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.setWordWrap(False);self.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.verticalHeader().hide();self.verticalHeader().setDefaultSectionSize(38);self.horizontalHeader().setHighlightSections(False)
        self.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Interactive);self.setColumnWidth(0,110)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
        self.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Fixed);self.setColumnWidth(1,76)
        self.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch);self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setAccessibleName('강의 유형 할 일 선택')
    def set_events(self,rows):self.event_model.set_events(rows)
    def update_event(self,event):self.event_model.update_event(event)
