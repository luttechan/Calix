"""Native diary workspace with password-only secret storage and bounded idle lock."""
from __future__ import annotations
import time
from PySide6.QtCore import Qt,QDate,QThread,QTimer,Signal,QEvent,QSize
from PySide6.QtGui import QTextCharFormat
from PySide6.QtWidgets import (QApplication,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,
    QLineEdit,QPlainTextEdit,QListWidget,QListWidgetItem,QStackedWidget,QSplitter,QDialog,QMessageBox)
from .controls import DateInput
from .diary_store import DiaryStore
from .diary_editor import DiaryEditor,FormatBar


def text(value='',name=''):
    label=QLabel(value);label.setObjectName(name);label.setTextFormat(Qt.TextFormat.PlainText);return label


class KeyTask(QThread):
    result=Signal(object)
    failed=Signal(str)
    def __init__(self,mode,password,header=None,new_password=None,parent=None):
        super().__init__(parent);self.mode=mode;self.password=password;self.header=header;self.new_password=new_password
    def run(self):
        from .diary_crypto import new_material,unlock_material,wrap_key,wipe,VaultError
        key=None
        try:
            if self.mode=='create':key,header=new_material(self.password)
            else:
                key=unlock_material(self.header,self.password)
                header=wrap_key(self.new_password,key) if self.mode=='change' else None
            self.result.emit((key,header));key=None
        except VaultError as exc:self.failed.emit(str(exc))
        except Exception:self.failed.emit('암호화 저장소를 열지 못했습니다.')
        finally:wipe(key);self.password='';self.new_password=None


class DiaryPane(QWidget):
    # QSplitter otherwise repeatedly asks nested rich-text layouts for hints.
    def sizeHint(self):return QSize(320,440)
    def minimumSizeHint(self):return QSize(170,150)


class DiaryPage(QWidget):
    work_finished=Signal()
    def sizeHint(self):return QSize(900,600)
    def minimumSizeHint(self):return QSize(420,280)
    def __init__(self,folder,parent=None):
        super().__init__(parent);self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,True);self.folder=folder;self.normal=DiaryStore(folder/'journals.db');self.vault=None
        self.secret=False;self.current_id=None;self.metadata={};self.loading=False;self.dirty=False
        self._pending_secret=None
        self.task=None;self.generation=0;self._closed=False;self.last_activity=time.monotonic()
        self.save_timer=QTimer(self);self.save_timer.setSingleShot(True);self.save_timer.setInterval(650);self.save_timer.timeout.connect(self.flush)
        self.idle_timer=QTimer(self);self.idle_timer.setInterval(15000);self.idle_timer.timeout.connect(self._idle);self.idle_timer.start()
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(14)
        row=QHBoxLayout();self.normal_button=QPushButton('일반 일기');self.secret_button=QPushButton('비밀 일기')
        for b,mode in ((self.normal_button,False),(self.secret_button,True)):
            b.setObjectName('segment');b.setCheckable(True);b.clicked.connect(lambda checked=False,s=mode:self.set_secret(s));row.addWidget(b)
        row.addStretch();self.saved=text('','muted');row.addWidget(self.saved);self.change_button=QPushButton('암호 변경');self.change_button.clicked.connect(self.change_password);row.addWidget(self.change_button)
        self.lock_button=QPushButton('잠그기');self.lock_button.clicked.connect(self.lock);row.addWidget(self.lock_button)
        self.new_button=QPushButton('일기 쓰기');self.new_button.setObjectName('primary');self.new_button.clicked.connect(self.new_entry);row.addWidget(self.new_button);layout.addLayout(row)
        self.stack=QStackedWidget();layout.addWidget(self.stack,1)
        self.locked=QWidget();outer=QVBoxLayout(self.locked);outer.addStretch();box=QWidget();box.setObjectName('diaryLock');box.setMaximumWidth(440);form=QVBoxLayout(box);form.setContentsMargins(28,28,28,28);form.setSpacing(16)
        self.lock_title=text('비밀 일기','heading');form.addWidget(self.lock_title);self.lock_note=text();self.lock_note.setWordWrap(True);form.addWidget(self.lock_note)
        self.password=QLineEdit();self.password.setEchoMode(QLineEdit.EchoMode.Password);self.password.setPlaceholderText('암호');self.password.setMaxLength(1024);self.password.setAccessibleName('비밀 일기 암호');form.addWidget(self.password)
        self.confirm=QLineEdit();self.confirm.setEchoMode(QLineEdit.EchoMode.Password);self.confirm.setPlaceholderText('암호 확인');self.confirm.setMaxLength(1024);self.confirm.setAccessibleName('비밀 일기 암호 확인');form.addWidget(self.confirm)
        self.unlock_button=QPushButton('잠금 해제');self.unlock_button.setObjectName('primary');self.unlock_button.clicked.connect(self.unlock);form.addWidget(self.unlock_button)
        self.password.returnPressed.connect(self.unlock);self.confirm.returnPressed.connect(self.unlock)
        self.lock_error=text('','formError');self.lock_error.setWordWrap(True);form.addWidget(self.lock_error);outer.addWidget(box,0,Qt.AlignmentFlag.AlignHCenter);outer.addStretch();self.stack.addWidget(self.locked)
        self.workspace=QSplitter(Qt.Orientation.Horizontal,self);self.workspace.setChildrenCollapsible(False);self.workspace.setHandleWidth(16)
        left=DiaryPane();lv=QVBoxLayout(left);lv.setContentsMargins(0,0,0,0);lv.setSpacing(10);self.search=QLineEdit();self.search.setPlaceholderText('제목이나 날짜 검색');self.search.setClearButtonEnabled(True);self.search.textChanged.connect(self._render_list);lv.addWidget(self.search)
        self.entries=QListWidget();self.entries.setObjectName('diaryList');self.entries.setMinimumWidth(170);self.entries.currentItemChanged.connect(self._select);lv.addWidget(self.entries,1);self.count=text('','muted');lv.addWidget(self.count);self.workspace.addWidget(left)
        right=DiaryPane();rv=QVBoxLayout(right);rv.setContentsMargins(4,0,0,0);rv.setSpacing(14);bar=QHBoxLayout();self.date=DateInput();self.date.changed.connect(self.mark_dirty);bar.addWidget(self.date);bar.addStretch();self.remove_button=QPushButton('삭제');self.remove_button.setObjectName('danger');self.remove_button.clicked.connect(self.remove_entry);bar.addWidget(self.remove_button);rv.addLayout(bar)
        self.title=QLineEdit();self.title.setObjectName('diaryTitle');self.title.setMaxLength(200);self.title.setPlaceholderText('오늘의 제목');self.title.setAccessibleName('일기 제목');self.title.textEdited.connect(self.mark_dirty);rv.addWidget(self.title)
        self.body=DiaryEditor();self.format_bar=FormatBar(self.body);rv.addWidget(self.format_bar);self.body.setPlaceholderText('오늘은 어떤 하루였나요?');self.body.setAccessibleName('일기 내용');self.body.textChanged.connect(self.mark_dirty);rv.addWidget(self.body,1)
        self.hint=text('내용은 자동으로 저장됩니다.','muted');rv.addWidget(self.hint);self.workspace.addWidget(right);self.workspace.setSizes([235,650]);self.workspace.setStretchFactor(1,1);self.stack.addWidget(self.workspace)
        QApplication.instance().installEventFilter(self);QApplication.instance().applicationStateChanged.connect(self._application_state)
        self.set_secret(False)

    def _store(self):return self.vault if self.secret else self.normal
    def _ensure_vault(self):
        if self.vault is None:
            from .diary_crypto import Vault
            self.vault=Vault(self.folder/'private-diary.db')
    def set_secret(self,value):
        if not self.flush():return
        self.lock();self.secret=bool(value);self.current_id=None;self._clear_editor();self.search.clear();self.metadata.clear()
        self.normal_button.setChecked(not self.secret);self.secret_button.setChecked(self.secret);self.lock_error.clear();self.saved.clear()
        self.body.setUndoRedoEnabled(not self.secret)
        if self.secret:
            try:self._ensure_vault()
            except Exception:self.lock_error.setText('암호화 저장소를 열지 못했습니다.');self.stack.setCurrentWidget(self.locked);return
            self._show_locked()
        else:self.stack.setCurrentWidget(self.workspace);self._load_metadata()
        self._buttons()
    def _buttons(self):
        opened=not self.secret or bool(self.vault and self.vault.unlocked)
        self.new_button.setEnabled(opened);self.lock_button.setVisible(self.secret and opened);self.change_button.setVisible(self.secret and opened)
        editable=opened and self.current_id is not None
        for control in (self.title,self.body,self.date,self.remove_button,self.format_bar):control.setEnabled(editable)
    def _show_locked(self):
        setup=not self.vault.initialized;self.stack.setCurrentWidget(self.locked);self.lock_title.setText('나만의 비밀 일기' if setup else '잠겨 있는 일기')
        self.lock_note.setText('12자 이상의 긴 암호를 정하세요. 잊으면 복구할 수 없습니다.' if setup else '암호를 입력하면 열립니다. 자리를 비우면 자동으로 잠깁니다.')
        self.confirm.setVisible(setup);self.unlock_button.setText('비밀 일기 만들기' if setup else '잠금 해제');self.password.clear();self.confirm.clear();self._buttons()
    def unlock(self):
        if self.task or not self.secret:return
        password=self.password.text();setup=not self.vault.initialized
        if setup and len(password)<12:self.lock_error.setText('암호는 12자 이상으로 정하세요.');return
        if setup and password!=self.confirm.text():self.lock_error.setText('두 암호가 다릅니다.');return
        self.password.clear();self.confirm.clear();self.lock_error.clear()
        self._start_task('create' if setup else 'unlock',password,None if setup else self.vault.header())
    def _start_task(self,mode,password,header,new_password=None):
        self.generation+=1;generation=self.generation;self.unlock_button.setEnabled(False);self.password.setEnabled(False);self.confirm.setEnabled(False);self.saved.setText('암호 확인 중')
        task=KeyTask(mode,password,header,new_password,self);self.task=task
        task.result.connect(lambda value:self._key_ready(generation,mode,value));task.failed.connect(lambda message:self._key_failed(generation,message));task.finished.connect(self._task_finished);task.start()
    def _key_ready(self,generation,mode,value):
        from .diary_crypto import wipe
        key,header=value
        try:
            if generation!=self.generation or self._closed:return
            if mode=='create':self.vault.initialize(key,header)
            elif mode=='change':self.vault.replace_header(header);self.saved.setText('암호 변경됨');return
            else:self.vault.activate(key)
            self.last_activity=time.monotonic();self.stack.setCurrentWidget(self.workspace);self.saved.setText('잠금 해제됨');self.body.setUndoRedoEnabled(False);self._load_metadata();self._buttons()
            if self._pending_secret:
                item_id,entry=self.vault.open_pending(self._pending_secret)
                self.loading=True;self.current_id=item_id;self.title.setText(entry['title']);self.date.setDate(QDate.fromString(entry['date'],'yyyy-MM-dd'))
                if entry.get('html'):self.body.setHtml(entry['html'])
                else:self.body.setPlainText(entry['body'])
                self.loading=False;self.dirty=True;self._pending_secret=None
                self.metadata[item_id]=dict(id=item_id,date=entry['date'],title=entry['title'])
                self._render_list();self._buttons();self.save_timer.start();self.saved.setText('저장 대기')
        except Exception:
            self.lock();self.lock_error.setText('저장소를 열지 못했습니다. 백업 상태를 확인하세요.')
        finally:wipe(key)
    def _key_failed(self,generation,message):
        if generation==self.generation:self.lock_error.setText(message);self.saved.setText('암호 확인 실패')
    def _task_finished(self):
        task=self.task;self.task=None
        if task:task.deleteLater()
        self.unlock_button.setEnabled(True);self.password.setEnabled(True);self.confirm.setEnabled(True);self.work_finished.emit()
    def _load_metadata(self):
        try:self.metadata={row['id']:row for row in self._store().summaries()}
        except Exception:self.lock();self.lock_error.setText('일기를 읽지 못했습니다. 저장소가 손상되었을 수 있습니다.');return
        self._render_list()
    def _render_list(self,*args):
        selected=self.current_id;query=self.search.text().strip().casefold();self.entries.blockSignals(True);self.entries.clear()
        rows=sorted(self.metadata.values(),key=lambda row:(row['date'],row['id']),reverse=True)
        for row in rows:
            if query and query not in (row['title']+' '+row['date']).casefold():continue
            item=QListWidgetItem((row['title'] or '제목 없는 일기')+'\n'+row['date'].replace('-','.'));item.setData(Qt.ItemDataRole.UserRole,row['id']);self.entries.addItem(item)
            if row['id']==selected:self.entries.setCurrentItem(item)
        self.entries.blockSignals(False);self.count.setText(f'{len(rows)}개의 일기')
    def _select(self,item,previous=None):
        if item is None:return
        key=item.data(Qt.ItemDataRole.UserRole)
        if key==self.current_id:return
        if not self.flush():self._render_list();return
        try:value=self._store().read(key)
        except Exception:self.saved.setText('일기를 읽지 못했습니다.');return
        self.loading=True;self.current_id=key;self.title.setText(value['title'])
        if value.get('html'):self.body.setHtml(value['html'])
        else:self.body.setCurrentCharFormat(QTextCharFormat());self.body.setPlainText(value['body'])
        self.date.setDate(QDate.fromString(value['date'],'yyyy-MM-dd'));self.loading=False;self.dirty=False;self._buttons()
    def _clear_editor(self):
        self.loading=True;self.title.clear();self.body.clear();self.body.setCurrentCharFormat(QTextCharFormat());self.body.document().clearUndoRedoStacks();self.date.setDate(QDate.currentDate());self.loading=False;self.dirty=False
    def new_entry(self):
        if not self.flush():return
        if self.secret and not self.vault.unlocked:return
        value=dict(date=QDate.currentDate().toString('yyyy-MM-dd'),title='',body='')
        try:key=self._store().save(value)
        except Exception:self.saved.setText('일기를 저장하지 못했습니다.');return
        self.current_id=None;self.metadata[key]=dict(id=key,date=value['date'],title='');self.search.clear();self._render_list()
        for index in range(self.entries.count()):
            item=self.entries.item(index)
            if item.data(Qt.ItemDataRole.UserRole)==key:self.entries.setCurrentItem(item);break
        self.title.setFocus()
    def mark_dirty(self,*args):
        if self.loading or self.current_id is None:return
        self.dirty=True;self.saved.setText('작성 중');self.save_timer.start();self.last_activity=time.monotonic()
    def flush(self):
        self.save_timer.stop()
        if self._pending_secret:
            self.saved.setText('잠금 해제 후 저장하세요.');return False
        if not self.dirty or self.current_id is None:return True
        value=dict(date=self.date.date().toString('yyyy-MM-dd'),title=self.title.text(),body=self.body.toPlainText(),html=self.body.toHtml())
        try:self._store().save(value,self.current_id)
        except Exception:self.saved.setText('저장 실패 / 저장 공간과 파일 권한을 확인하세요.');return False
        self.dirty=False;self.metadata[self.current_id]=dict(id=self.current_id,date=value['date'],title=value['title']);self._render_list();self.saved.setText('자동 저장됨');return True
    def discard_pending(self):
        self.save_timer.stop();self._pending_secret=None;self.dirty=False;self.current_id=None;self._clear_editor()
    def remove_entry(self):
        if self.current_id is None:return
        if QMessageBox.question(self,'일기 삭제','이 일기를 삭제할까요?')!=QMessageBox.StandardButton.Yes:return
        key=self.current_id
        try:self._store().remove(key)
        except Exception:self.saved.setText('삭제하지 못했습니다.');return
        self.save_timer.stop();self.dirty=False;self.current_id=None;self.metadata.pop(key,None);self._clear_editor();self._render_list();self._buttons();self.saved.setText('일기 삭제됨')
    def lock(self):
        if self._closed:return
        self.generation+=1
        if not self.secret:return
        saved=self.flush()
        if not saved and self.dirty and self.current_id and self.vault and self.vault.unlocked:
            value=dict(date=self.date.date().toString('yyyy-MM-dd'),title=self.title.text(),body=self.body.toPlainText(),html=self.body.toHtml())
            self._pending_secret=self.vault.seal_pending(self.current_id,value)
        self.current_id=None;self._clear_editor();self.search.clear();self.metadata.clear();self.entries.clear();self.count.clear();self.password.clear();self.confirm.clear()
        if self.vault:self.vault.lock();self._show_locked()
        self.saved.setText('잠김' if saved else '저장하지 못한 내용이 있습니다. 저장 공간을 확인하세요.')
    def _idle(self):
        if self.secret and time.monotonic()-self.last_activity>=300:self.lock()
    def _application_state(self,state):
        if not self._closed and state!=Qt.ApplicationState.ApplicationActive:self.lock()
    def eventFilter(self,watched,event):
        if self.secret and event.type() in (QEvent.Type.KeyPress,QEvent.Type.MouseButtonPress,QEvent.Type.Wheel):self.last_activity=time.monotonic()
        return False
    def hideEvent(self,event):
        if not self._closed:self.flush();self.lock()
        super().hideEvent(event)
    def change_password(self):
        if self.task or not self.vault.unlocked:return
        dialog=QDialog(self);dialog.setWindowTitle('비밀 일기 암호 변경');dialog.resize(420,300);layout=QVBoxLayout(dialog);layout.setContentsMargins(24,24,24,24);layout.setSpacing(12)
        layout.addWidget(text('새 암호로 보호하기','section'));note=text('기존 백업은 당시의 암호로 열립니다.');note.setWordWrap(True);layout.addWidget(note);fields=[]
        for title in ('현재 암호','새 암호: 12자 이상','새 암호 확인'):
            edit=QLineEdit();edit.setEchoMode(QLineEdit.EchoMode.Password);edit.setPlaceholderText(title);edit.setMaxLength(1024);layout.addWidget(edit);fields.append(edit)
        error=text('','formError');layout.addWidget(error);save=QPushButton('암호 변경');save.setObjectName('primary');layout.addWidget(save)
        def accept():
            if len(fields[1].text())<12:error.setText('새 암호는 12자 이상으로 정하세요.');return
            if fields[1].text()!=fields[2].text():error.setText('두 암호가 다릅니다.');return
            dialog.accept()
        save.clicked.connect(accept)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            old,new=fields[0].text(),fields[1].text()
            for edit in fields:edit.clear()
            self._start_task('change',old,self.vault.header(),new)
        dialog.deleteLater()
    def prepare_close(self):
        if not self.flush():return False
        self.lock();self.generation+=1
        return self.task is None
    def shutdown(self):
        self._closed=True;self._pending_secret=None;self.idle_timer.stop();self.save_timer.stop();QApplication.instance().removeEventFilter(self)
        QApplication.instance().applicationStateChanged.disconnect(self._application_state)
        self.normal.close()
        if self.vault:self.vault.close()
