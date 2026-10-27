"""Native rich text with an intentionally small formatting toolbar."""
from PySide6.QtCore import Qt,Signal,QMimeData
from PySide6.QtGui import QColor,QFont,QTextCharFormat,QTextCursor,QAction,QKeySequence
from PySide6.QtWidgets import QTextEdit,QWidget,QHBoxLayout,QToolButton,QColorDialog,QMenu,QApplication


class DiaryEditor(QTextEdit):
    def __init__(self,parent=None):
        super().__init__(parent);self.setAcceptRichText(False);self.setObjectName('diaryBody')
        self.setTabChangesFocus(False)
    def loadResource(self,kind,url):
        # A diary never fetches remote images or reads local files embedded in HTML.
        return None
    def insertFromMimeData(self,source):
        if source.hasText():self.textCursor().insertText(source.text())
    def canInsertFromMimeData(self,source):return source.hasText()
    def setHtml(self,value):
        import re
        family=QApplication.font().family()
        def normalize(match):
            names=r'(?:Malgun Gothic|맑은 고딕|Pretendard(?: Variable)?)'
            css=re.sub(r'font-family\s*:\s*(?:\''+names+r'\'|"'+names+r'"|'+names+r')',lambda _:f"font-family:'{family}'",match.group(1),flags=re.IGNORECASE)
            return 'style="'+css+'"'
        # Update only legacy CSS, never a diary's literal text or saved file.
        value=re.sub(r'style="([^"]*)"',normalize,value,flags=re.IGNORECASE)
        super().setHtml(value)


class FormatBar(QWidget):
    def __init__(self,editor,parent=None):
        super().__init__(parent);self.editor=editor;row=QHBoxLayout(self);row.setContentsMargins(0,0,0,0);row.setSpacing(5);self.buttons={}
        for key,title,tip,shortcut in (('bold','B','굵게','Ctrl+B'),('italic','I','기울임','Ctrl+I'),('underline','U','밑줄','Ctrl+U'),('strike','S','취소선','')):
            button=QToolButton();button.setObjectName('formatButton');button.setText(title);button.setCheckable(True);button.setFixedSize(34,34);button.setAccessibleName(tip);button.setToolTip(tip+(' / '+shortcut if shortcut else ''));button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            font=button.font();font.setBold(key=='bold');font.setItalic(key=='italic');font.setUnderline(key=='underline');font.setStrikeOut(key=='strike');button.setFont(font)
            button.clicked.connect(lambda checked=False,k=key:self.toggle(k,checked));row.addWidget(button);self.buttons[key]=button
            if shortcut:
                action=QAction(editor);action.setShortcut(QKeySequence(shortcut));action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut);action.triggered.connect(lambda checked=False,k=key:self.toggle(k,not self.buttons[k].isChecked()));editor.addAction(action)
        color=QToolButton();color.setText('글자색');color.setObjectName('formatColor');color.setFocusPolicy(Qt.FocusPolicy.NoFocus);color.setToolTip('선택한 글자의 색상');color.clicked.connect(self.pick_color);row.addWidget(color)
        reset=QToolButton();self.reset_button=reset;reset.setText('서식 지우기');reset.setObjectName('formatColor');reset.setFocusPolicy(Qt.FocusPolicy.NoFocus);reset.setToolTip('선택한 글자를 기본 서식으로');reset.clicked.connect(self.reset);row.addWidget(reset);row.addStretch()
        editor.currentCharFormatChanged.connect(self.sync);editor.cursorPositionChanged.connect(lambda:self.sync(editor.currentCharFormat()));self.sync(editor.currentCharFormat())
    def merge(self,fmt):
        self.editor.mergeCurrentCharFormat(fmt);self.editor.setFocus();self.sync(self.editor.currentCharFormat())
    def toggle(self,key,checked):
        fmt=QTextCharFormat()
        if key=='bold':fmt.setFontWeight(QFont.Weight.Bold if checked else QFont.Weight.Normal)
        elif key=='italic':fmt.setFontItalic(checked)
        elif key=='underline':fmt.setFontUnderline(checked)
        elif key=='strike':fmt.setFontStrikeOut(checked)
        self.merge(fmt)
    def sync(self,fmt):
        values=dict(bold=fmt.fontWeight()>=QFont.Weight.Bold,italic=fmt.fontItalic(),underline=fmt.fontUnderline(),strike=fmt.fontStrikeOut())
        for key,button in self.buttons.items():button.setChecked(values[key])
    def pick_color(self):
        cursor=self.editor.textCursor();color=QColorDialog.getColor(self.editor.textColor(),self,'글자색',QColorDialog.ColorDialogOption.DontUseNativeDialog)
        if color.isValid():
            self.editor.setTextCursor(cursor);fmt=QTextCharFormat();fmt.setForeground(color);self.merge(fmt)
    def reset(self):
        cursor=self.editor.textCursor();fmt=QTextCharFormat()
        if cursor.hasSelection():cursor.setCharFormat(fmt)
        self.editor.setCurrentCharFormat(fmt);self.editor.setFocus();self.sync(fmt)
