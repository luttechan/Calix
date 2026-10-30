from pathlib import Path
import sqlite3
import pytest
from learning_calendar.paths import migrate_legacy_data

def legacy(tmp_path):
    source=tmp_path/'legacy';source.mkdir();db=sqlite3.connect(source/'learning.db');db.execute('CREATE TABLE proof(value TEXT)');db.execute("INSERT INTO proof VALUES('preserved')");db.commit();db.close();return source

def test_windows_temporary_rename_denial_retries_without_changing_source(tmp_path,monkeypatch):
    source=legacy(tmp_path);original=(source/'learning.db').read_bytes();rename=Path.rename;calls=[]
    def temporary(path,target):
        calls.append(path)
        if len(calls)<3:raise PermissionError('synthetic temporary lock')
        return rename(path,target)
    monkeypatch.setattr(Path,'rename',temporary);target=tmp_path/'new/Calix'
    assert migrate_legacy_data(target,source) and len(calls)==3
    assert (source/'learning.db').read_bytes()==original
    db=sqlite3.connect(target/'learning.db');assert db.execute('SELECT value FROM proof').fetchone()==('preserved',);db.close()

def test_persistent_denial_is_bounded_and_preserves_both_copies(tmp_path,monkeypatch):
    source=legacy(tmp_path);original=(source/'learning.db').read_bytes();calls=[]
    def denied(path,target):calls.append(path);raise PermissionError('synthetic persistent lock')
    monkeypatch.setattr(Path,'rename',denied);target=tmp_path/'new/Calix'
    with pytest.raises(PermissionError):migrate_legacy_data(target,source)
    assert len(calls)==6 and not target.exists() and (source/'learning.db').read_bytes()==original
    assert (calls[-1]/'learning.db').is_file()

def test_concurrent_destination_is_never_replaced(tmp_path,monkeypatch):
    source=legacy(tmp_path);target=tmp_path/'new/Calix';calls=[]
    def concurrent(path,destination):
        calls.append(path);destination.mkdir();(destination/'proof.txt').write_text('other instance');raise PermissionError('synthetic concurrent creation')
    monkeypatch.setattr(Path,'rename',concurrent)
    with pytest.raises(PermissionError):migrate_legacy_data(target,source)
    assert len(calls)==1 and (target/'proof.txt').read_text()=='other instance'
