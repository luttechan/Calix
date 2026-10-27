import pytest
from PySide6.QtWidgets import QApplication
from learning_calendar.diary_view import DiaryPage
from learning_calendar.diary_crypto import new_material,unlock_material,wipe,VaultError

PASSWORD='synthetic-long-passphrase-only'


def test_disk_failure_locks_plaintext_but_recovers_encrypted_draft(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([]);page=DiaryPage(tmp_path)
    page.set_secret(True);key,header=new_material(PASSWORD);page.vault.initialize(key,header);wipe(key)
    page.stack.setCurrentWidget(page.workspace);page.new_entry();item_id=page.current_id
    page.title.setText('synthetic-private-title');page.body.setPlainText('synthetic-private-unsaved-body')
    with monkeypatch.context() as failure:
        def full_disk(*args,**kwargs):raise OSError('synthetic full disk')
        failure.setattr(page.vault,'save',full_disk)
        page.lock()
        assert not page.vault.unlocked and page._pending_secret
        assert not page.title.text() and not page.body.toPlainText() and not page.metadata
        assert b'synthetic-private-unsaved-body' not in page._pending_secret[1]
        assert not page.flush() and not page.prepare_close()
        key=unlock_material(page.vault.header(),PASSWORD)
        page._key_ready(page.generation,'unlock',(key,None))
        assert page._pending_secret is None and page.dirty
        assert page.current_id==item_id and page.body.toPlainText()=='synthetic-private-unsaved-body'
    assert page.flush() and page.vault.read(item_id)['body']=='synthetic-private-unsaved-body'
    page.shutdown();page.deleteLater();app.processEvents()


def test_encrypted_draft_authentication_and_explicit_discard(tmp_path):
    app=QApplication.instance() or QApplication([]);page=DiaryPage(tmp_path)
    page.set_secret(True);key,header=new_material(PASSWORD);page.vault.initialize(key,header);wipe(key)
    pending=page.vault.seal_pending('0'*32,dict(date='2026-10-28',title='draft',body='private'))
    damaged=(pending[0],pending[1][:-1]+bytes([pending[1][-1]^1]))
    with pytest.raises(VaultError):page.vault.open_pending(damaged)
    page._pending_secret=pending;page.discard_pending()
    assert page._pending_secret is None and not page.dirty
    page.shutdown();page.deleteLater();app.processEvents()
