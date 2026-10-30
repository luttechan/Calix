"""On-demand native file dialogs and the existing verified update installer."""
from pathlib import Path
import json,sys,os,hashlib,subprocess,ctypes

def install(path,digest,parent):
    path=Path(path).resolve()
    import tempfile
    base=Path(tempfile.gettempdir()).resolve()
    if path.name!='Calix-Setup.exe' or path.parent.parent!=base or not path.parent.name.startswith('Calix-update-'):return 2
    with path.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=digest:return 2
    if os.name=='nt':
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.restype=ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint32]
        kernel.CloseHandle.argtypes=[ctypes.c_void_p]
        handle=kernel.OpenProcess(0x100000,False,parent)
        if handle:
            try:
                if kernel.WaitForSingleObject(handle,30000)!=0:return 2
            finally:kernel.CloseHandle(handle)
    subprocess.Popen([str(path)],cwd=path.parent)
    return 0

def run(mode,folder):
    from PySide6.QtWidgets import QApplication,QFileDialog,QMessageBox
    from learning_calendar.app_identity import apply_app_icon
    from learning_calendar.fonts import apply_korean_font
    app=QApplication([]);app.setApplicationName('Calix');apply_app_icon(app);apply_korean_font(app)
    def emit(value):print(json.dumps(value,ensure_ascii=False),flush=True)
    if mode=='updates':
        from learning_calendar import design
        design.VERSION='1.4.0'
        from learning_calendar.update_dialog import UpdateDialog
        dialog=UpdateDialog()
        def ready(path):
            with Path(path).open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
            # Leave this verified file for the detached installer after application exit.
            dialog.installer=None;emit(dict(installer=path,digest=digest));dialog.accept()
        dialog.install_requested.connect(ready);dialog.show();return app.exec()
    from engine_api import EngineAPI
    from learning_calendar.local_backup import write_backup,read_backup,restore_backup
    api=EngineAPI(folder)
    try:
        if mode=='backup':
            path,_=QFileDialog.getSaveFileName(None,'개인 자료 백업','Calix-backup.calix','Calix 백업 (*.calix)')
            if path:write_backup(path,api.store,folder);emit(dict(message='백업됨'))
        elif mode=='restore':
            path,_=QFileDialog.getOpenFileName(None,'백업 복원','','Calix 백업 (*.calix)')
            if path:
                value=read_backup(path,api.store.get_meta('canvas_user_id'))
                if QMessageBox.question(None,'백업 복원','현재 개인 자료를 백업 파일로 바꾸시겠습니까?')==QMessageBox.StandardButton.Yes:
                    from datetime import datetime
                    recovery=Path(folder)/('recovery-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.calix')
                    write_backup(recovery,api.store,folder);restore_backup(value,api.store,folder);emit(dict(message='복원됨'))
    except Exception as error:
        QMessageBox.warning(None,'Calix',str(error) if isinstance(error,ValueError) else '자료를 처리하지 못했습니다.')
    finally:api.close()
    return 0
