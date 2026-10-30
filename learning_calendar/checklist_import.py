"""Explicit checklist imports; filtering never selects hidden rows."""
from PySide6.QtCore import Qt,QAbstractTableModel,QModelIndex,QSortFilterProxyModel
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QComboBox,QPushButton,QTableView,QHeaderView,QAbstractItemView

class ImportModel(QAbstractTableModel):
    def __init__(self,events,parent=None):
        super().__init__(parent);self.events=list(events);self.selected=set();self.search=[(e.title+' '+e.course_name).casefold() for e in self.events]
    def rowCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self.events)
    def columnCount(self,parent=QModelIndex()):return 0 if parent.isValid() else 4
    def headerData(self,section,orientation,role=Qt.ItemDataRole.DisplayRole):
        if orientation==Qt.Orientation.Horizontal and role==Qt.ItemDataRole.DisplayRole:return ('일정','과목','유형','기한')[section]
    def data(self,index,role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():return None
        e=self.events[index.row()]
        if role==Qt.ItemDataRole.CheckStateRole and index.column()==0:return Qt.CheckState.Checked if index.row() in self.selected else Qt.CheckState.Unchecked
        if role==Qt.ItemDataRole.ToolTipRole:return e.title+' / '+e.course_name
        if role==Qt.ItemDataRole.DisplayRole:return (e.title,e.course_name,'과제' if e.kind=='assignment' else '영상',e.due.strftime('%m.%d %H:%M') if e.due else '기한 없음')[index.column()]
    def flags(self,index):
        return super().flags(index)|(Qt.ItemFlag.ItemIsUserCheckable if index.column()==0 else Qt.ItemFlag.NoItemFlags)
    def setData(self,index,value,role=Qt.ItemDataRole.EditRole):
        if not index.isValid() or index.column()!=0 or role!=Qt.ItemDataRole.CheckStateRole:return False
        if value in (Qt.CheckState.Checked,Qt.CheckState.Checked.value):self.selected.add(index.row())
        else:self.selected.discard(index.row())
        self.dataChanged.emit(index,index,[role]);return True

class ImportFilter(QSortFilterProxyModel):
    def __init__(self,parent=None):super().__init__(parent);self.query='';self.kind=None;self.course=None
    def filterAcceptsRow(self,row,parent):
        model=self.sourceModel();e=model.events[row]
        return (self.kind is None or e.kind==self.kind) and (self.course is None or e.course_id==self.course) and (not self.query or self.query in model.search[row])

class ImportDialog(QDialog):
    def __init__(self,events,repo,parent=None):
        super().__init__(parent);self.setWindowTitle('일괄 가져오기');self.resize(800,560)
        imported={r['source_key'] for r in repo.db.execute('SELECT source_key FROM checklist_tasks WHERE trashed=0 AND source_key IS NOT NULL')}
        events=[e for e in events if not e.manual and e.kind in ('assignment','movie') and e.key not in imported]
        layout=QVBoxLayout(self);layout.setContentsMargins(24,24,24,20);layout.setSpacing(14)
        heading=QLabel('가져올 일정 선택');heading.setObjectName('section');layout.addWidget(heading)
        filters=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText('일정 또는 과목 검색');self.search.setClearButtonEnabled(True);filters.addWidget(self.search,1)
        self.kind=QComboBox();self.kind.addItem('모든 유형',None);self.kind.addItem('과제','assignment');self.kind.addItem('영상','movie');filters.addWidget(self.kind)
        self.course=QComboBox();self.course.addItem('모든 과목',None)
        for cid,name in sorted({e.course_id:e.course_name for e in events}.items(),key=lambda item:item[1]):self.course.addItem(name,cid)
        filters.addWidget(self.course);layout.addLayout(filters)
        self.model=ImportModel(events,self);self.proxy=ImportFilter(self);self.proxy.setSourceModel(self.model)
        self.table=QTableView();self.table.setAccessibleName('가져올 일정 선택');self.table.setModel(self.proxy);self.table.verticalHeader().hide();self.table.verticalHeader().setDefaultSectionSize(42);self.table.setShowGrid(False);self.table.setWordWrap(False);self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        for col,width in ((1,160),(2,70),(3,110)):self.table.setColumnWidth(col,width)
        layout.addWidget(self.table,1);actions=QHBoxLayout();all_button=QPushButton('전체 선택');all_button.clicked.connect(lambda:self.select_visible(True));actions.addWidget(all_button);none=QPushButton('선택 해제');none.clicked.connect(lambda:self.select_visible(False));actions.addWidget(none);self.count=QLabel();actions.addWidget(self.count);actions.addStretch();cancel=QPushButton('취소');cancel.clicked.connect(self.reject);actions.addWidget(cancel);self.submit=QPushButton('가져오기');self.submit.setObjectName('primary');self.submit.clicked.connect(self.accept);actions.addWidget(self.submit);layout.addLayout(actions)
        self.model.dataChanged.connect(self.update_count);self.search.textChanged.connect(self.filter_changed);self.kind.currentIndexChanged.connect(self.filter_changed);self.course.currentIndexChanged.connect(self.filter_changed);self.update_count()
        from .popup_tools import add_hints
        add_hints(self)
    def filter_changed(self,*args):
        self.proxy.beginFilterChange();self.proxy.query=self.search.text().strip().casefold();self.proxy.kind=self.kind.currentData();self.proxy.course=self.course.currentData();self.proxy.endFilterChange(QSortFilterProxyModel.Direction.Rows)
    def select_visible(self,value):
        rows={self.proxy.mapToSource(self.proxy.index(i,0)).row() for i in range(self.proxy.rowCount())}
        if value:self.model.selected.update(rows)
        else:self.model.selected.difference_update(rows)
        if self.model.rowCount():self.model.dataChanged.emit(self.model.index(0,0),self.model.index(self.model.rowCount()-1,0),[Qt.ItemDataRole.CheckStateRole])
        self.update_count()
    def update_count(self,*args):self.count.setText(f'{len(self.model.selected)}개 선택');self.submit.setEnabled(bool(self.model.selected))
    def selected_events(self):return [self.model.events[i] for i in sorted(self.model.selected)]
