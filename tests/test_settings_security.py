from PySide6.QtWidgets import QApplication,QDialog
from learning_calendar import dialogs


def test_explicit_saved_account_removal_and_password_clear(monkeypatch):
    app=QApplication.instance() or QApplication([]);calls=[]
    monkeypatch.setattr(dialogs,'read_account',lambda:'synthetic-id')
    monkeypatch.setattr(dialogs,'store_account',lambda *args:calls.append(args))
    dialog=dialogs.SettingsDialog();dialog.password.setText('synthetic-new-password');dialog.remove.click()
    assert calls==[('',)] and dialog.result()==QDialog.DialogCode.Accepted
    assert dialog.student.text()=='' and dialog.password.text()==''
    dialog.deleteLater();app.processEvents()
    canceled=dialogs.SettingsDialog();canceled.password.setText('synthetic-only');canceled.reject()
    assert canceled.password.text()=='' and calls==[('',)]
    canceled.deleteLater();app.processEvents()
