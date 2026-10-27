"""Native QListView/QStyledItemDelegate rendering with a virtualized data model."""
from PySide6.QtCore import QAbstractListModel,QModelIndex,Qt,QSize,QRect,Signal,QEvent
from PySide6.QtGui import QColor,QFont,QFontMetrics,QPalette,QIcon
from PySide6.QtWidgets import QListView,QStyledItemDelegate,QAbstractItemView,QStyleOptionViewItem,QStyleOptionButton,QStyle,QApplication
from .models import deadline_display
from .design import colors,icon,glass_enabled
from .text_safety import tooltip_text
EVENT_ROLE=int(Qt.ItemDataRole.UserRole)+1

class EventListModel(QAbstractListModel):
    completion_requested=Signal(object,bool)
    def __init__(self,parent=None):super().__init__(parent);self.rows=[]
    def rowCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self.rows)
    def data(self,index,role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0<=index.row()<len(self.rows):return None
        e=self.rows[index.row()]
        if role==EVENT_ROLE:return e
        if role==Qt.ItemDataRole.UserRole:return e.key
        if role==Qt.ItemDataRole.CheckStateRole and e.manual:return Qt.CheckState.Checked if e.completed else Qt.CheckState.Unchecked
        due=e.due.strftime('%m.%d  %H:%M') if e.due else '기한 없음'
        if role==Qt.ItemDataRole.DisplayRole:
            return ('★ ' if e.starred else '')+e.title+'\n'+e.course_name+'\n'+due+'   '+deadline_display(e)[0]+('   메모' if e.note else '')
        if role==Qt.ItemDataRole.AccessibleTextRole:return f'{e.title} / {e.course_name} / {deadline_display(e)[0]}'
        if role==Qt.ItemDataRole.DecorationRole:return icon('custom',e.type_color) if e.type_id is not None else icon('video' if e.kind=='movie' else 'assignment')
        if role==Qt.ItemDataRole.ForegroundRole:return QColor(colors()['muted'] if e.completed else colors()['ink'])
        if role==Qt.ItemDataRole.ToolTipRole:return tooltip_text(f'{e.title}\n{e.course_name}\n{due}\n{deadline_display(e)[0]}')
    def flags(self,index):
        flags=super().flags(index)
        if index.isValid() and self.rows[index.row()].manual:flags|=Qt.ItemFlag.ItemIsUserCheckable
        return flags
    def setData(self,index,value,role=Qt.ItemDataRole.EditRole):
        if role==Qt.ItemDataRole.CheckStateRole and index.isValid() and self.rows[index.row()].manual:
            self.completion_requested.emit(self.rows[index.row()],value in (Qt.CheckState.Checked,Qt.CheckState.Checked.value));return True
        return False
    def set_events(self,rows):
        rows=list(rows)
        if rows==self.rows:return False
        self.beginResetModel();self.rows=rows;self.endResetModel();return True

class EventDelegate(QStyledItemDelegate):
    def __init__(self,parent=None):
        super().__init__(parent);self._font_key=None;self._text_styles={}
    def text_style(self,base,size,weight):
        key=base.key()
        if key!=self._font_key:self._font_key=key;self._text_styles.clear()
        style=(size,weight)
        if style not in self._text_styles:
            font=QFont(base);font.setPixelSize(size);font.setWeight(weight)
            self._text_styles[style]=(font,QFontMetrics(font))
        return self._text_styles[style]
    def sizeHint(self,option,index):return QSize(200,86)
    def paint(self,painter,option,index):
        event=index.data(EVENT_ROLE)
        if event is None:return
        c=colors();rect=option.rect.adjusted(4,4,-4,-4)
        painter.save();painter.setRenderHint(painter.RenderHint.Antialiasing)
        selected=bool(option.state&QStyle.StateFlag.State_Selected);hover=bool(option.state&QStyle.StateFlag.State_MouseOver)
        fill=QColor(c['soft'] if selected else c['hover'] if hover else c['surface'])
        painter.setPen(QColor(c['accent'] if selected else c['line']));painter.setBrush(fill);painter.drawRoundedRect(rect,14 if glass_enabled() else 12,14 if glass_enabled() else 12)
        if event.manual:
            from .check_indicator import paint_check
            paint_check(painter,QRect(rect.left()+12,rect.top()+16,18,18),event.completed,c)
        else:(icon('custom',event.type_color) if event.type_id is not None else icon('video' if event.kind=='movie' else 'assignment')).paint(painter,QRect(rect.left()+12,rect.top()+17,20,20))
        due=event.due.strftime('%m.%d %H:%M') if event.due else '기한 없음'
        lines=[(('★ ' if event.starred else '')+event.title,14,QFont.Weight.DemiBold,c['muted'] if event.completed else c['ink']),
               ((event.type_label+' / ' if event.type_id is not None else '')+event.course_name,12,QFont.Weight.Normal,c['muted']),
               (due+'   '+deadline_display(event)[0],12,QFont.Weight.Normal,c['muted'])]
        for n,(value,size,weight,color) in enumerate(lines):
            text_option=QStyleOptionViewItem(option);text_option.rect=QRect(rect.left()+42,rect.top()+8+n*21,max(1,rect.width()-54),22)
            text_option.font,text_option.fontMetrics=self.text_style(option.font,size,weight)
            text_option.text=text_option.fontMetrics.elidedText(value,Qt.TextElideMode.ElideRight,text_option.rect.width());text_option.icon=QIcon()
            text_option.features=QStyleOptionViewItem.ViewItemFeature.HasDisplay;text_option.state=QStyle.StateFlag.State_Enabled
            text_option.displayAlignment=Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter;text_option.palette.setColor(QPalette.ColorRole.Text,QColor(color))
            QApplication.style().drawControl(QStyle.ControlElement.CE_ItemViewItem,text_option,painter,option.widget)
        painter.restore()
    def editorEvent(self,event,model,option,index):
        item=index.data(EVENT_ROLE)
        if item and item.manual:
            mouse=event.type()==QEvent.Type.MouseButtonRelease and QRect(option.rect.left()+16,option.rect.top()+20,24,24).contains(event.position().toPoint())
            keyboard=event.type()==QEvent.Type.KeyPress and event.key()==Qt.Key.Key_Space
            if mouse or keyboard:return model.setData(index,Qt.CheckState.Unchecked if item.completed else Qt.CheckState.Checked,Qt.ItemDataRole.CheckStateRole)
        return super().editorEvent(event,model,option,index)

class EventList(QListView):
    completion_requested=Signal(object,bool)
    def __init__(self,parent=None):
        super().__init__(parent);self.event_model=EventListModel(self);self.setModel(self.event_model)
        self.event_model.completion_requested.connect(self.completion_requested)
        self.setItemDelegate(EventDelegate(self));self.setUniformItemSizes(True);self.setWordWrap(False)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setMouseTracking(True);self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.empty_text='일정이 없습니다'
        from PySide6.QtWidgets import QLabel
        self.empty_label=QLabel(self.empty_text,self.viewport());self.empty_label.setObjectName('muted')
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter);self.empty_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    def set_events(self,rows):
        selected=self.currentIndex().data(Qt.ItemDataRole.UserRole);scroll=self.verticalScrollBar().value()
        if self.event_model.set_events(rows):
            if selected:
                for i,e in enumerate(self.event_model.rows):
                    if e.key==selected:self.setCurrentIndex(self.event_model.index(i));break
            self.verticalScrollBar().setValue(scroll)
        self.empty_label.setText(self.empty_text);self.empty_label.setVisible(not self.event_model.rows);self.viewport().update()
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'empty_label'):self.empty_label.setGeometry(self.viewport().rect())
