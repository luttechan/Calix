"""Calix assets and a non-destructive migration of the previous app data."""
from pathlib import Path
import os,sys,sqlite3,shutil
from uuid import uuid4

def asset_path(name):
    if getattr(sys,'frozen',False):
        folder=Path(sys.executable).resolve().parent
        external=(folder.parent if folder.name=='app' else folder)/'asset'/name
        if external.is_file():return external
    return Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))/'asset'/name

def migrate_legacy_data(target,legacy=None):
    target=Path(target)
    if target.exists():return False
    legacy=Path(legacy) if legacy else Path(os.environ.get('APPDATA',''))/'BUFS-LearningTools'/'BUFS Learning Calendar'
    if not legacy.is_dir() or not (legacy/'learning.db').is_file():return False
    target.parent.mkdir(parents=True,exist_ok=True)
    stage=target.parent/('calix-migration-'+uuid4().hex);stage.mkdir()
    for db in legacy.glob('learning*.db'):
        source=sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True)
        destination=sqlite3.connect(stage/db.name)
        try:source.backup(destination)
        finally:destination.close();source.close()
    for name in ('settings.json','canvas_session.dpapi'):
        if (legacy/name).is_file():shutil.copy2(legacy/name,stage/name)
    (stage/'migration.txt').write_text('Imported from BUFS Learning Calendar. Original files retained.',encoding='utf-8')
    # Windows can briefly deny a directory rename while a scanner holds a
    # newly written database. Keep the staged copy and retry for at most 775 ms.
    from time import sleep
    for attempt in range(6):
        try:stage.rename(target);break
        except PermissionError:
            if attempt==5 or target.exists():raise
            sleep(.025*2**attempt)
    return True
