from PySide6.QtWidgets import QApplication,QWidget,QVBoxLayout
from PySide6.QtCore import Qt
from learning_calendar.schedule_preview import PreviewLabel


def test_labels_defer_unstyled_font_work_but_fit_on_show_and_reopen(monkeypatch):
    app=QApplication.instance() or QApplication([]);label=PreviewLabel()
    def forbidden():raise AssertionError('unparented labels must not resolve fonts')
    with monkeypatch.context() as patch:
        patch.setattr(label,'fontMetrics',forbidden)
        label.setText('아직 배치하지 않은 글자')
    parent=QWidget();parent.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True);parent.resize(120,60)
    label.setMinimumWidth(0);QVBoxLayout(parent).addWidget(label);parent.show();app.processEvents()
    value='긴 일정 이름 '*30;label.setText(value)
    assert label.full_text==value and label.fontMetrics().horizontalAdvance(label.text())<=label.contentsRect().width()
    parent.hide();label.setText(value+'추가');parent.show();app.processEvents()
    assert label.fontMetrics().horizontalAdvance(label.text())<=label.contentsRect().width()
    parent.close();parent.deleteLater();app.processEvents()
