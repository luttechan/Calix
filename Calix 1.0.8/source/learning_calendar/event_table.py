"""Native, virtualized deadline table shared by home schedule sections."""
from datetime import datetime
from PySide6.QtCore import Qt,QAbstractTableModel,QModelIndex,QSize,Signal,QRect,QEvent
from PySide6.QtGui import QColor,QPen
from PySide6.QtWidgets import QTableView,QHeaderView,QAbstractItemView,QStyledItemDelegate,QLabel,QStyleOptionViewItem,QStyle,QApplication
from .models import KST,deadline_display
from .design import colors,category_colors,type_tokens
from .event_view import EVENT_ROLE

class ScheduleModel(QAbstractTableModel):
    completion_requested=Signal(object,bool)
    HEADERS=('Type','과목','일정명','기한','남은 시간')
    def __init__(self,parent=None):super().__init__(parent);self.rows=[];self.now=datetime.now(KST)
    def rowCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self.rows)
    def columnCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self.HEADERS)
    def headerData(self,section,orientation,role=Qt.ItemDataRole.DisplayRole):
        if orientation==Qt.Orientation.Horizontal and role==Qt.ItemDataRole.DisplayRole:return self.HEADERS[section]
    def data(self,index,role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0<=index.row()<len(self.rows):return None
        e=self.rows[index.row()];column=index.column();status,tone=deadline_display(e,self.now)
        texts=(e.type_label,e.course_name,e.title,
               e.due.strftime('%m.%d %H:%M') if e.due else '기한 없음',status.removeprefix('마감 '))
        if role==EVENT_ROLE:return e
        if role==Qt.ItemDataRole.UserRole:return e.key
        if role==Qt.ItemDataRole.CheckStateRole and column==0 and e.manual:return Qt.CheckState.Checked if e.completed else Qt.CheckState.Unchecked
        if role in (Qt.ItemDataRole.DisplayRole,Qt.ItemDataRole.ToolTipRole,Qt.ItemDataRole.AccessibleTextRole):return texts[column]
        if role==Qt.ItemDataRole.TextAlignmentRole:return int(Qt.AlignmentFlag.AlignVCenter| (Qt.AlignmentFlag.AlignCenter if column==0 else Qt.AlignmentFlag.AlignLeft))
        if role==Qt.ItemDataRole.ForegroundRole:
            if column==0:return QColor(type_tokens(e.type_color)['ink'] if e.type_id is not None else category_colors()['assignment_ink' if e.kind=='assignment' else 'movie_ink'])
            return QColor(colors()['ink'] if column in (1,2) else colors()['muted'])
    def flags(self,index):
        flags=super().flags(index)
        if index.isValid() and index.column()==0 and self.rows[index.row()].manual:flags|=Qt.ItemFlag.ItemIsUserCheckable
        return flags
    def setData(self,index,value,role=Qt.ItemDataRole.EditRole):
        if role==Qt.ItemDataRole.CheckStateRole and index.isValid() and self.rows[index.row()].manual:
            self.completion_requested.emit(self.rows[index.row()],value in (Qt.CheckState.Checked,Qt.CheckState.Checked.value));return True
        return False
    def set_events(self,rows,now=None):
        rows=list(rows);self.now=now or datetime.now(KST)
        if rows!=self.rows:
            self.beginResetModel();self.rows=rows;self.endResetModel();return True
        if rows:self.dataChanged.emit(self.index(0,3),self.index(len(rows)-1,4))
        return False

class TypeDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        event=index.data(EVENT_ROLE);c=category_colors();prefix='assignment' if event.kind=='assignment' else 'movie'
        tokens=type_tokens(event.type_color) if event.type_id is not None else dict(ink=c[prefix+'_ink'],bg=c[prefix+'_bg'],line=c[prefix+'_line'])
        painter.save();painter.setRenderHint(painter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(tokens['line']),1));painter.setBrush(QColor(tokens['bg']))
        painter.drawRoundedRect(option.rect.adjusted(27 if event.manual else 5,6,-5,-6),4,4);painter.restore()
        text_option=QStyleOptionViewItem(option);self.initStyleOption(text_option,index)
        text_option.features &= ~QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
        if event.manual:
            from .check_indicator import paint_check
            paint_check(painter,QRect(option.rect.left()+7,option.rect.center().y()-8,16,16),event.completed,colors())
            text_option.rect.adjust(25,0,0,0)
        text_option.state &= ~QStyle.StateFlag.State_Selected
        QApplication.style().drawControl(QStyle.ControlElement.CE_ItemViewItem,text_option,painter,option.widget)
    def editorEvent(self,event,model,option,index):
        item=index.data(EVENT_ROLE)
        if item and item.manual:
            mouse=event.type()==QEvent.Type.MouseButtonRelease and QRect(option.rect.left()+3,option.rect.center().y()-12,25,25).contains(event.position().toPoint())
            keyboard=event.type()==QEvent.Type.KeyPress and event.key()==Qt.Key.Key_Space
            if mouse or keyboard:return model.setData(index,Qt.CheckState.Unchecked if item.completed else Qt.CheckState.Checked,Qt.ItemDataRole.CheckStateRole)
            return False
        return super().editorEvent(event,model,option,index)

class ScheduleTable(QTableView):
    completion_requested=Signal(object,bool)
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setObjectName('scheduleTable')
        self.event_model=ScheduleModel(self)
        self.setModel(self.event_model)
        self.setAccessibleName('남은 일정')
        self.event_model.completion_requested.connect(self.completion_requested)
        self.setShowGrid(False);self.setWordWrap(False);self.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.verticalHeader().hide();self.verticalHeader().setDefaultSectionSize(46)
        header=self.horizontalHeader();header.setSectionsClickable(False);header.setStretchLastSection(False)
        for column,width in ((0,98),(1,140),(3,112),(4,100)):
            header.setSectionResizeMode(column,QHeaderView.ResizeMode.Interactive);self.setColumnWidth(column,width)
        header.setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch);header.setMinimumSectionSize(56)
        self.setItemDelegateForColumn(0,TypeDelegate(self));self.setMinimumHeight(170)
        self.empty_label=QLabel('남은 일정이 없습니다',self.viewport());self.empty_label.setObjectName('muted')
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter);self.empty_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    def set_events(self,rows,now=None):
        key=self.currentIndex().data(Qt.ItemDataRole.UserRole);scroll=self.verticalScrollBar().value()
        if self.event_model.set_events(rows,now) and key:
            for row,e in enumerate(self.event_model.rows):
                if e.key==key:self.setCurrentIndex(self.event_model.index(row,0));break
        self.verticalScrollBar().setValue(scroll);self.empty_label.setVisible(not self.event_model.rows);self.viewport().update()
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'empty_label'):self.empty_label.setGeometry(self.viewport().rect())
