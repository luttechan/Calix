"""A native editable table with persistent sections and colored statuses."""
import sqlite3
from PySide6.QtCore import Qt,QAbstractTableModel,QSortFilterProxyModel,QModelIndex,QDateTime,Signal,QTimer,QUrl,QEvent,QRect
from PySide6.QtGui import QColor,QDesktopServices,QKeySequence,QShortcut
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QLineEdit,QCheckBox,QTabBar,QTableView,QHeaderView,QAbstractItemView,QStyledItemDelegate,QComboBox,QDateTimeEdit,QInputDialog,QMenu,QDialog,QDialogButtonBox,QFormLayout)
from .checklist_store import ChecklistStore
from .models import parse_datetime
from .design import colors,type_tokens
from .text_safety import tooltip_text
from .timetable_view import ColorPicker
from .controls import CheckToggle as QCheckBox

ROW_ROLE=Qt.ItemDataRole.UserRole+41
SORT_ROLE=Qt.ItemDataRole.UserRole+42
COLUMNS=[('할 일','title'),('기한','due_at'),('분류','category'),('내 역할','role'),('담당 교수','professor'),('상태','status_id'),('비고','note')]

def prepared(row):
    row=dict(row);due=parse_datetime(row.get('due_at'))
    row['_sort']=tuple((due.timestamp() if due else None) if i==1 else row['status_id'] if i==5 else str(row.get(key) or '').casefold() for i,(_,key) in enumerate(COLUMNS))
    row['_search']=' '.join(str(row.get(k) or '') for _,k in COLUMNS).casefold()+' '+row['status_name'].casefold()
    return row


class ChecklistModel(QAbstractTableModel):
    failed=Signal(str);changed=Signal()
    def __init__(self,repo,parent=None):super().__init__(parent);self.repo=repo;self.rows=[];self.read_only=False;self.events=[];self.sessions=[];self.trash=False
    def rowCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self.rows)
    def columnCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(COLUMNS)
    def headerData(self,section,orientation,role=Qt.ItemDataRole.DisplayRole):
        if role==Qt.ItemDataRole.DisplayRole and orientation==Qt.Orientation.Horizontal:return COLUMNS[section][0]
        if role==Qt.ItemDataRole.ToolTipRole and orientation==Qt.Orientation.Horizontal:return COLUMNS[section][0]+' / 클릭하여 정렬'
    def data(self,index,role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0<=index.row()<len(self.rows):return None
        row=self.rows[index.row()];column=index.column();key=COLUMNS[column][1];value=row.get(key)
        if role==ROW_ROLE:return row
        if role==Qt.ItemDataRole.CheckStateRole and column==0:return Qt.CheckState.Checked if row['status_kind']=='done' else Qt.CheckState.Unchecked
        if role==Qt.ItemDataRole.EditRole:return value or ''
        if role==Qt.ItemDataRole.DisplayRole:
            if column==1:
                due=parse_datetime(value);return due.strftime('%Y.%m.%d %H:%M') if due else ''
            return row['status_name'] if column==5 else value or ''
        if role==SORT_ROLE:
            if column==1:
                due=parse_datetime(value);return due.timestamp() if due else None
            return row['status_id'] if column==5 else str(value or '').casefold()
        if role==Qt.ItemDataRole.ToolTipRole:
            if column==5 and row.get('source_key'):return '내 진행 상태 / 학교 제출 상태와 시청 기록은 별도로 관리합니다.'
            return tooltip_text(self.data(index))
        if role==Qt.ItemDataRole.ForegroundRole:
            if row['status_kind'] in ('done','cancel'):return QColor(colors()['muted'])
            if column==1 and row.get('due_at'):
                from datetime import datetime
                from .models import KST
                if parse_datetime(row['due_at'])<datetime.now(KST):return QColor('#D94B61')
    def flags(self,index):
        value=Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable
        if index.isValid() and not self.read_only:
            value|=Qt.ItemFlag.ItemIsEditable
            if index.column()==0:value|=Qt.ItemFlag.ItemIsUserCheckable
        return value
    def setData(self,index,value,role=Qt.ItemDataRole.EditRole):
        if self.read_only or not index.isValid():return False
        row=self.rows[index.row()];field=COLUMNS[index.column()][1]
        try:
            if role==Qt.ItemDataRole.CheckStateRole and index.column()==0:
                self.repo.toggle(row,value in (Qt.CheckState.Checked,Qt.CheckState.Checked.value))
            elif role==Qt.ItemDataRole.EditRole:self.repo.save(row,field,value)
            else:return False
            updated=next((r for r in self.repo.rows(row['section_id'],self.events,self.sessions,self.trash) if r['id']==row['id']),None)
            if updated:self.rows[index.row()]=prepared(updated)
            self.dataChanged.emit(self.index(index.row(),0),self.index(index.row(),6));self.changed.emit();return True
        except (ValueError,sqlite3.Error) as exc:self.failed.emit(str(exc) if isinstance(exc,ValueError) else '저장하지 못했습니다.');return False
    def load(self,rows,events,sessions,trash=False):
        self.beginResetModel();self.rows=[prepared(row) for row in rows];self.events=events;self.sessions=sessions;self.trash=trash;self.endResetModel()


class ChecklistFilter(QSortFilterProxyModel):
    def __init__(self,parent=None):super().__init__(parent);self.query='';self.pending_only=False;self.setSortRole(SORT_ROLE)
    def filterAcceptsRow(self,row,parent):
        value=self.sourceModel().rows[row]
        return (not self.pending_only or value['status_kind']=='open') and (not self.query or self.query in value['_search'])
    def lessThan(self,left,right):
        rows=self.sourceModel().rows;left_row=rows[left.row()];right_row=rows[right.row()]
        a=left_row['_sort'][left.column()];b=right_row['_sort'][right.column()]
        if a is None or b is None:
            if a is None and b is None:return left_row['id']<right_row['id']
            return b is None if self.sortOrder()==Qt.SortOrder.AscendingOrder else a is None
        return a<b if a!=b else left_row['id']<right_row['id']


class ChecklistDelegate(QStyledItemDelegate):
    def __init__(self,view):super().__init__(view);self.view=view
    def createEditor(self,parent,option,index):
        col=index.column()
        if col==5:
            editor=QComboBox(parent)
            for s in self.view.repo.statuses():editor.addItem(s['name'],s['id'])
            return editor
        if col==1:
            editor=QDateTimeEdit(parent);editor.setCalendarPopup(True);editor.setDisplayFormat('yyyy.MM.dd HH:mm');return editor
        if col==2:
            editor=QComboBox(parent);editor.setEditable(True);editor.addItem('')
            for course in self.view.courses:editor.addItem(course.name)
            return editor
        editor=QLineEdit(parent);editor.setMaxLength({'title':200,'role':100,'professor':120,'note':20000}.get(COLUMNS[col][1],200));return editor
    def setEditorData(self,editor,index):
        value=index.data(Qt.ItemDataRole.EditRole)
        if index.column()==5:editor.setCurrentIndex(max(0,editor.findData(value)))
        elif index.column()==1:
            date=parse_datetime(value);editor.setDateTime(QDateTime(date) if date else QDateTime.currentDateTime())
        elif index.column()==2:editor.setCurrentText(str(value))
        else:editor.setText(str(value));editor.selectAll()
    def setModelData(self,editor,model,index):
        col=index.column()
        value=editor.currentData() if col==5 else editor.dateTime().toPython().astimezone().isoformat() if col==1 else editor.currentText() if col==2 else editor.text()
        model.setData(index,value,Qt.ItemDataRole.EditRole)
    def paint(self,painter,option,index):
        if index.column()==0:
            from PySide6.QtWidgets import QStyleOptionViewItem,QStyle,QApplication
            from .check_indicator import paint_check
            opt=QStyleOptionViewItem(option);self.initStyleOption(opt,index)
            style=opt.widget.style() if opt.widget else QApplication.style();rect=style.subElementRect(QStyle.SubElement.SE_ItemViewItemCheckIndicator,opt,opt.widget)
            super().paint(painter,option,index);paint_check(painter,rect,index.data(ROW_ROLE)['status_kind']=='done',colors());return
        if index.column()!=5:return super().paint(painter,option,index)
        from PySide6.QtWidgets import QStyleOptionViewItem,QStyle,QApplication
        from PySide6.QtCore import QRectF
        opt=QStyleOptionViewItem(option);self.initStyleOption(opt,index);title=opt.text;opt.text=''
        style=opt.widget.style() if opt.widget else QApplication.style();style.drawControl(QStyle.ControlElement.CE_ItemViewItem,opt,painter,opt.widget)
        row=index.data(ROW_ROLE);tokens=type_tokens(row['status_color']);rect=QRectF(option.rect.adjusted(8,8,-8,-8));rect.setWidth(min(rect.width(),option.fontMetrics.horizontalAdvance(title)+22))
        painter.save();painter.setRenderHint(painter.RenderHint.Antialiasing);painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor(tokens['bg']));painter.drawRoundedRect(rect,6,6)
        painter.setFont(option.font);painter.setPen(QColor(tokens['ink']));painter.drawText(rect,Qt.AlignmentFlag.AlignCenter,option.fontMetrics.elidedText(title,Qt.TextElideMode.ElideRight,int(rect.width()-12)));painter.restore()


class StatusEditor(QDialog):
    def __init__(self,repo,parent=None):
        super().__init__(parent);self.repo=repo;self.setWindowTitle('상태 편집');self.resize(420,480)
        form=QFormLayout(self);self.choose=QComboBox();self.choose.addItem('새 상태',None)
        for s in repo.statuses():self.choose.addItem(s['name'],s['id'])
        form.addRow('상태',self.choose);self.name=QLineEdit();self.name.setMaxLength(24);form.addRow('이름',self.name)
        self.kind=QComboBox()
        for name,value in [('진행할 일','open'),('완료','done'),('취소','cancel')]:self.kind.addItem(name,value)
        form.addRow('처리',self.kind);self.color=ColorPicker(columns=8);form.addRow('색상',self.color);self.error=QLabel();self.error.setTextFormat(Qt.TextFormat.PlainText);form.addRow(self.error)
        actions=QHBoxLayout();remove=QPushButton('삭제');remove.clicked.connect(self.remove);actions.addWidget(remove);actions.addStretch();save=QPushButton('저장');save.setObjectName('primary');save.clicked.connect(self.save);actions.addWidget(save);form.addRow(actions)
        self.choose.currentIndexChanged.connect(self.load)
    def load(self):
        row=next((s for s in self.repo.statuses() if s['id']==self.choose.currentData()),None)
        self.name.setText(row['name'] if row else '');self.color.set_color(row['color'] if row else '#7582E6');self.kind.setCurrentIndex(self.kind.findData(row['kind'] if row else 'open'));self.kind.setEnabled(self.choose.currentData() not in (4,5));self.error.clear()
    def save(self):
        try:self.repo.save_status(self.name.text(),self.color.value,self.kind.currentData(),self.choose.currentData());self.accept()
        except (ValueError,sqlite3.Error) as exc:self.error.setText(str(exc) if isinstance(exc,ValueError) else '저장하지 못했습니다.')
    def remove(self):
        if self.choose.currentData() is None:return
        try:self.repo.delete_status(self.choose.currentData());self.accept()
        except (ValueError,sqlite3.Error) as exc:self.error.setText(str(exc) if isinstance(exc,ValueError) else '삭제하지 못했습니다.')


class ChecklistView(QWidget):
    def __init__(self,store,parent=None):
        super().__init__(parent);self.repo=ChecklistStore(store);self.events=[];self.sessions=[];self.courses=[];self.read_only=False;self.show_trash=False;self.undo_rows=[];self.popup=None;self._checkbox_click=False
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(12)
        top=QHBoxLayout();self.sections=QTabBar();self.sections.setExpanding(False);self.sections.setDrawBase(False);top.addWidget(self.sections);add=QPushButton('+ 섹션');add.clicked.connect(self.add_section);self.add_section_button=add;top.addWidget(add);top.addStretch();self.section_menu=QPushButton('섹션 편집');self.section_menu.clicked.connect(self.edit_section);top.addWidget(self.section_menu);layout.addLayout(top)
        tools=QHBoxLayout();self.import_assignment=QCheckBox('과제 불러오기');self.import_movie=QCheckBox('영상 불러오기')
        for box,kind in [(self.import_assignment,'assignment'),(self.import_movie,'movie')]:box.setChecked(kind in self.repo.included());box.toggled.connect(self.import_changed);tools.addWidget(box)
        self.search=QLineEdit();self.search.setPlaceholderText('할 일 검색');self.search.setClearButtonEnabled(True);tools.addWidget(self.search,1)
        self.pending=QCheckBox('미완료만');tools.addWidget(self.pending);self.trash_button=QPushButton('휴지통');self.trash_button.setCheckable(True);self.trash_button.toggled.connect(self.trash_changed);tools.addWidget(self.trash_button)
        self.status_button=QPushButton('상태 편집');self.status_button.clicked.connect(self.edit_status);tools.addWidget(self.status_button)
        self.add_button=QPushButton('할 일 추가');self.add_button.setObjectName('primary');self.add_button.clicked.connect(self.add_task);tools.addWidget(self.add_button);layout.addLayout(tools)
        self.table=QTableView();self.table.setObjectName('checklistTable');self.table.setAccessibleName('할 일 체크리스트');self.model=ChecklistModel(self.repo,self);self.proxy=ChecklistFilter(self);self.proxy.setSourceModel(self.model);self.table.setModel(self.proxy)
        self.table.setItemDelegate(ChecklistDelegate(self));self.table.setSortingEnabled(True);self.table.sortByColumn(1,Qt.SortOrder.AscendingOrder)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.table.verticalHeader().hide();self.table.verticalHeader().setDefaultSectionSize(44);self.table.setAlternatingRowColors(False);self.table.setShowGrid(False)
        self.table.viewport().installEventFilter(self);self.table.clicked.connect(self.open_field);self.table.activated.connect(self.open_field)
        shortcut=QShortcut(QKeySequence('F2'),self.table,activated=lambda:self.open_field(self.table.currentIndex()));shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        header=self.table.horizontalHeader();header.setSectionsMovable(False);header.setMinimumSectionSize(90)
        for i,width in enumerate((240,152,150,110,110,110,200)):self.table.setColumnWidth(i,width)
        header.setStretchLastSection(True);header.sectionClicked.connect(lambda *_:self.close_popup());layout.addWidget(self.table,1)
        foot=QHBoxLayout();self.count=QLabel();self.count.setTextFormat(Qt.TextFormat.PlainText);foot.addWidget(self.count);foot.addStretch();self.message=QLabel();self.message.setTextFormat(Qt.TextFormat.PlainText);foot.addWidget(self.message);layout.addLayout(foot)
        self.model.failed.connect(self.message.setText);self.model.changed.connect(self.update_count);self.sections.currentChanged.connect(self.refresh)
        self.search_timer=QTimer(self);self.search_timer.setSingleShot(True);self.search_timer.setInterval(100);self.search_timer.timeout.connect(self.filter_changed);self.search.textChanged.connect(lambda:self.search_timer.start());self.pending.toggled.connect(self.filter_changed)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu);self.table.customContextMenuRequested.connect(self.context_menu)
        for key,action in [('Delete',self.delete_selected),('Ctrl+Z',self.undo_delete)]:
            shortcut=QShortcut(QKeySequence(key),self.table,activated=action);shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.table.viewport().setMouseTracking(True)
        self.reload_sections()
        from .popup_tools import add_hints
        add_hints(self);self.search.setToolTip('할 일, 분류, 역할, 교수, 비고 검색');self.table.setToolTip('항목 클릭: 편집 / 열 제목 클릭: 정렬')
        self.add_button.setToolTip('할 일 추가 (Ctrl+N)');self.trash_button.setToolTip('삭제한 할 일 확인 및 복원')
    def section_id(self):return self.sections.tabData(self.sections.currentIndex()) or 1
    def flush_editor(self):
        self.close_popup()
        from PySide6.QtWidgets import QApplication
        focus=QApplication.focusWidget()
        if focus and self.table.isAncestorOf(focus):self.table.setFocus(Qt.FocusReason.OtherFocusReason)
    def close_popup(self,commit=True):
        popup=self.popup
        if popup:
            if commit:popup.close()
            else:popup.reject()
    def hideEvent(self,event):self.close_popup();super().hideEvent(event)
    def eventFilter(self,obj,event):
        if obj is self.table.viewport() and event.type()==QEvent.Type.MouseButtonPress:
            index=self.table.indexAt(event.position().toPoint());self._checkbox_click=index.isValid() and index.column()==0 and event.position().x()<self.table.visualRect(index).left()+30
        elif obj is self.table.viewport() and event.type()==QEvent.Type.MouseMove:
            self.table.viewport().setCursor(Qt.CursorShape.PointingHandCursor if self.table.indexAt(event.position().toPoint()).isValid() else Qt.CursorShape.ArrowCursor)
        return super().eventFilter(obj,event)
    def open_field(self,index):
        if self._checkbox_click:self._checkbox_click=False;return
        if self.read_only or not index.isValid():return
        row=index.data(ROW_ROLE)
        if not row:return
        key=row['id'];column=index.column();rect=self.table.visualRect(index);anchor=QRect(self.table.viewport().mapToGlobal(rect.topLeft()),rect.size())
        self.close_popup();row=next((r for r in self.model.rows if r['id']==key),None)
        if not row:return
        choices=[]
        if column==5:choices=self.repo.statuses()
        elif column in (2,3,4):
            key=COLUMNS[column][1];values={str(r.get(key) or '') for r in self.model.rows}
            if column==2:values.update(c.name for c in self.courses)
            elif column==3:values.update(('작성','자료 조사','발표','검토'))
            elif column==4:values.update(s.get('professor','') for s in self.sessions)
            choices=sorted(filter(None,values),key=str.casefold)
        from .checklist_popup import FieldPopup
        popup=FieldPopup(column,dict(row),choices,lambda value:self.save_field(row['id'],column,value),self);self.popup=popup;token=id(popup)
        popup.failed.connect(self.message.setText)
        def clear(*args):
            if self.popup is not None and id(self.popup)==token:self.popup=None
        popup.finished.connect(clear);popup.destroyed.connect(clear)
        from .popup_tools import place_popup
        place_popup(popup,anchor);popup.show()
    def save_field(self,key,column,value):
        if self.read_only:return False
        row=next((i for i,r in enumerate(self.model.rows) if r['id']==key),None)
        if row is None:return False
        saved=self.model.setData(self.model.index(row,column),value)
        if saved:self.message.setText('저장됨')
        return saved
    def reload_sections(self,selected=None):
        selected=selected or self.section_id();self.sections.blockSignals(True)
        while self.sections.count():self.sections.removeTab(0)
        for row in self.repo.sections():i=self.sections.addTab(row['name']);self.sections.setTabData(i,row['id']);self.sections.setCurrentIndex(i if row['id']==selected else self.sections.currentIndex())
        self.sections.blockSignals(False);self.add_section_button.setEnabled(not self.read_only and self.sections.count()<5);self.refresh()
    def set_data(self,store,events,courses,sessions,read_only=False):
        self.close_popup(commit=self.repo.store is store)
        if self.repo.store is not store:self.undo_rows=[]
        self.repo=ChecklistStore(store);self.model.repo=self.repo;self.events=list(events);self.courses=list(courses);self.sessions=list(sessions);self.read_only=read_only;self.model.read_only=read_only
        for widget in (self.import_assignment,self.import_movie,self.add_button,self.status_button,self.section_menu):widget.setEnabled(not read_only)
        for box,kind in [(self.import_assignment,'assignment'),(self.import_movie,'movie')]:box.blockSignals(True);box.setChecked(kind in self.repo.included());box.blockSignals(False)
        self.reload_sections()
    def refresh(self,*args):
        self.close_popup()
        school=self.section_id()==1
        self.import_assignment.setVisible(school);self.import_movie.setVisible(school)
        self.model.load(self.repo.rows(self.section_id(),self.events,self.sessions,self.show_trash),self.events,self.sessions,self.show_trash);self.update_count()
    def update_count(self):
        total=self.proxy.rowCount();done=sum(self.model.rows[self.proxy.mapToSource(self.proxy.index(i,0)).row()]['status_kind']=='done' for i in range(total))
        self.count.setText(f'{total}개 / 완료 {done}개')
    def import_changed(self):
        if self.read_only:return
        try:self.repo.set_included([kind for box,kind in [(self.import_assignment,'assignment'),(self.import_movie,'movie')] if box.isChecked()]);self.refresh()
        except (ValueError,sqlite3.Error):self.message.setText('설정을 저장하지 못했습니다.')
    def filter_changed(self):
        self.close_popup()
        modern=hasattr(self.proxy,'beginFilterChange') and hasattr(self.proxy,'endFilterChange')
        if modern:self.proxy.beginFilterChange()
        self.proxy.query=self.search.text().strip().casefold();self.proxy.pending_only=self.pending.isChecked()
        if modern:self.proxy.endFilterChange(QSortFilterProxyModel.Direction.Rows)
        else:self.proxy.invalidateFilter()
        self.update_count()
    def trash_changed(self,value):self.show_trash=value;self.refresh()
    def add_section(self):
        if self.read_only:return
        name,ok=QInputDialog.getText(self,'섹션 추가','이름')
        if ok:
            try:self.reload_sections(self.repo.save_section(name))
            except (ValueError,sqlite3.Error) as exc:self.message.setText(str(exc) if isinstance(exc,ValueError) else '저장하지 못했습니다.')
    def edit_section(self):
        if self.read_only:return
        menu=QMenu(self);rename=menu.addAction('이름 변경');remove=menu.addAction('섹션 삭제');remove.setEnabled(self.section_id()!=1);choice=menu.exec(self.section_menu.mapToGlobal(self.section_menu.rect().bottomLeft()));menu.deleteLater()
        if choice==rename:
            name,ok=QInputDialog.getText(self,'섹션 이름','이름',text=self.sections.tabText(self.sections.currentIndex()))
            if ok:
                try:self.repo.save_section(name,self.section_id());self.reload_sections()
                except (ValueError,sqlite3.Error) as exc:self.message.setText(str(exc) if isinstance(exc,ValueError) else '저장하지 못했습니다.')
        elif choice==remove:
            try:self.repo.delete_section(self.section_id());self.reload_sections(1)
            except (ValueError,sqlite3.Error):self.message.setText('섹션을 삭제하지 못했습니다.')
    def edit_status(self):
        if self.read_only:return
        dialog=StatusEditor(self.repo,self)
        if dialog.exec():self.refresh()
        dialog.deleteLater()
    def add_task(self):
        if self.read_only:return
        self.close_popup();self.search.clear();self.pending.setChecked(False);self.filter_changed()
        if self.show_trash:self.trash_button.setChecked(False)
        try:key=self.repo.add(self.section_id());self.refresh()
        except (ValueError,sqlite3.Error):self.message.setText('할 일을 저장하지 못했습니다.');return
        for i,row in enumerate(self.model.rows):
            if row['id']==key:index=self.proxy.mapFromSource(self.model.index(i,0));self.table.setCurrentIndex(index);self.table.scrollTo(index);self.open_field(index);break
    def selected_rows(self):return [index.data(ROW_ROLE) for index in self.table.selectionModel().selectedRows()]
    def delete_selected(self):
        if self.read_only:return
        rows=self.selected_rows()
        if not rows:return
        try:self.repo.trash(rows,not self.show_trash);self.undo_rows=(rows,not self.show_trash);self.refresh()
        except (ValueError,sqlite3.Error):self.message.setText('휴지통을 저장하지 못했습니다.')
    def undo_delete(self):
        if self.read_only or not self.undo_rows:return
        rows,trashed=self.undo_rows
        try:self.repo.trash(rows,not trashed);self.undo_rows=[];self.refresh()
        except (ValueError,sqlite3.Error):self.message.setText('복원하지 못했습니다.')
    def context_menu(self,pos):
        index=self.table.indexAt(pos)
        if not index.isValid():return
        row=index.data(ROW_ROLE);menu=QMenu(self);original=menu.addAction('학교에서 열기');original.setEnabled(bool(row.get('url')))
        date=menu.addAction('기한 없음');date.setEnabled(not self.read_only);remove=menu.addAction('복원' if self.show_trash else '휴지통으로 이동');remove.setEnabled(not self.read_only)
        chosen=menu.exec(self.table.viewport().mapToGlobal(pos))
        menu.deleteLater()
        if chosen==original:QDesktopServices.openUrl(QUrl(row['url']))
        elif chosen==date:self.model.setData(self.proxy.mapToSource(index.siblingAtColumn(1)),'')
        elif chosen==remove:self.delete_selected()
