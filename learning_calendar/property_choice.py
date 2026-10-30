"""One native surface for property search, direct entry and explicit selection."""
from PySide6.QtCore import Qt,Signal,QEvent,QSize,QRectF
from PySide6.QtGui import QStandardItemModel,QStandardItem,QPainter,QColor,QPen
from PySide6.QtWidgets import QWidget,QVBoxLayout,QLineEdit,QListView,QLabel,QStyledItemDelegate,QStyle
from .design import colors,icon

VALUE_ROLE=int(Qt.ItemDataRole.UserRole)+1
TEXT_ROLE=VALUE_ROLE+1
CURRENT_ROLE=VALUE_ROLE+2


class ChoiceDelegate(QStyledItemDelegate):
    def sizeHint(self,option,index):return QSize(240,36)
    def paint(self,painter,option,index):
        c=colors();painter.save();painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect=option.rect.adjusted(2,1,-2,-1)
        active=bool(option.state&(QStyle.StateFlag.State_Selected|QStyle.StateFlag.State_MouseOver))
        painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor(c['soft'] if active else c['surface']));painter.drawRoundedRect(QRectF(rect),6,6)
        left=rect.left()+10;decoration=index.data(Qt.ItemDataRole.DecorationRole)
        if decoration:
            decoration.paint(painter,left,rect.center().y()-8,16,16);left+=24
        text_rect=rect.adjusted(left-rect.left(),0,-34,0);painter.setFont(option.font);painter.setPen(QColor(c['ink']))
        text=painter.fontMetrics().elidedText(str(index.data() or ''),Qt.TextElideMode.ElideRight,text_rect.width())
        painter.drawText(text_rect,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,text)
        if index.data(CURRENT_ROLE):
            x=rect.right()-20;y=rect.center().y();painter.setPen(QPen(QColor(c['accent']),1.6,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin));painter.drawLine(x-4,y,x-1,y+3);painter.drawLine(x-1,y+3,x+5,y-4)
        painter.restore()


class PropertyChoice(QWidget):
    activated=Signal(int)
    submitted=Signal()
    def __init__(self,editable,parent=None):
        super().__init__(parent);self.editable=editable;self._choices=[];self._selected=None;self._current='';self._navigated=False
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(8)
        self.input=QLineEdit();self.input.setObjectName('propertySearch');self.input.setClearButtonEnabled(True);self.input.setPlaceholderText('검색 또는 직접 입력' if editable else '상태 검색');self.input.installEventFilter(self);layout.addWidget(self.input)
        self.options=QListView();self.options.setObjectName('propertyOptions');self.options.setUniformItemSizes(True);self.options.setMouseTracking(True);self.options.setFocusPolicy(Qt.FocusPolicy.NoFocus);self.options.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);self.options.setItemDelegate(ChoiceDelegate(self.options))
        self._model=QStandardItemModel(self);self.options.setModel(self._model);self.options.clicked.connect(self.choose);layout.addWidget(self.options)
        self.empty=QLabel('검색 결과 없음');self.empty.setObjectName('muted');layout.addWidget(self.empty);self.empty.hide()
        self.input.textEdited.connect(self.filter);self.input.returnPressed.connect(self.submit)
        self.setFocusProxy(self.input)
    def set_choices(self,choices,current):
        self._choices=list(choices);self._selected=current if not self.editable else None
        self._current=str(current or '') if self.editable else next((text for text,value,color in choices if value==current),'')
        self.input.setText(self._current if self.editable else '');self.filter('')
    def filter(self,query):
        self._navigated=False;self._model.clear();query=query.strip().casefold()
        for text,value,color in self._choices:
            if query and query not in text.casefold():continue
            item=QStandardItem(text);item.setEditable(False);item.setData(value,VALUE_ROLE);item.setData(text,TEXT_ROLE);item.setData((text==self._current) if self.editable else value==self._selected,CURRENT_ROLE);item.setToolTip(text)
            if color:item.setIcon(icon('custom',color))
            self._model.appendRow(item)
        count=self._model.rowCount();self.options.setVisible(bool(count));self.options.setFixedHeight(min(224,count*36+8));self.empty.setVisible(not count)
        self.options.setCurrentIndex(self._model.index(-1,0))
    def choose(self,index):
        if not index.isValid():return
        self._selected=index.data(VALUE_ROLE);self._current=index.data(TEXT_ROLE)
        self.input.setText(self._current);self.activated.emit(index.row())
    def submit(self):
        index=self.options.currentIndex()
        if index.isValid() and self._navigated:self.choose(index)
        elif self.editable:self.submitted.emit()
        elif self._model.rowCount()==1:self.choose(self._model.index(0,0))
        elif not self.input.text():self.submitted.emit()
    def eventFilter(self,obj,event):
        if obj is self.input and event.type()==QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Down,Qt.Key.Key_Up):
            count=self._model.rowCount()
            if count:
                row=self.options.currentIndex().row();step=1 if event.key()==Qt.Key.Key_Down else -1
                row=(0 if step>0 else count-1) if row<0 else max(0,min(count-1,row+step))
                self.options.setCurrentIndex(self._model.index(row,0));self.options.scrollTo(self.options.currentIndex());self._navigated=True
            return True
        return super().eventFilter(obj,event)
    def currentText(self):return self.input.text() if self.editable else self._current
    def currentData(self):return self._selected
    def lineEdit(self):return self.input
    def count(self):return self._model.rowCount()
    def model(self):return self._model
    def view(self):return self.options
    def findData(self,value):return next((i for i in range(self.count()) if self._model.index(i,0).data(VALUE_ROLE)==value),-1)
    def showPopup(self):self.input.setFocus();self.input.selectAll()
    def hidePopup(self):self.options.clearSelection()
