"""The shell becomes visible before Chromium imports; sessions are saved on verified success."""
from pathlib import Path

def run(output,existing=None,theme='sky',ready_file=None,control_server=None):
    from .app_identity import configure_windows_identity,apply_app_icon
    configure_windows_identity()
    from PySide6.QtCore import QCoreApplication,QEvent,Qt
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    from PySide6.QtWidgets import QApplication,QDialog
    from .fonts import apply_korean_font
    from .design import stylesheet,apply_palette
    from .login import CampusLoginDialog
    from .cookies import write_cookies,canvas_session_available
    app=QApplication([]);app.setStyle('Fusion');apply_korean_font(app);apply_palette(app,theme);app.setStyleSheet(stylesheet(theme))
    apply_app_icon(app)
    dialog=CampusLoginDialog(existing,ready_file,resident=bool(control_server))
    if control_server:
        from .browser_service import BrowserService
        app.setQuitOnLastWindowClosed(False);service=BrowserService(app,dialog,output,control_server,app)
        dialog.show();app.exec();accepted=False
    else:accepted=dialog.exec()==QDialog.DialogCode.Accepted
    result=2
    if accepted and canvas_session_available(dialog.session_rows):
        write_cookies(Path(output),dialog.session_rows);result=0
    profile_dir=dialog._profile_dir
    dialog.dispose();dialog.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    app.processEvents()
    if profile_dir:
        # Chromium can release its disk handles shortly after QObject teardown.
        # Retry only the exact temporary profile created by this process.
        import time
        from PySide6.QtCore import QDir
        temporary=Path(profile_dir.path()).resolve();temp_root=Path(QDir.tempPath()).resolve()
        if temporary.parent==temp_root and temporary.name.startswith('Calix-login-'):
            for _ in range(60):
                if profile_dir.remove():break
                app.processEvents();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);time.sleep(.05)
    return 0 if control_server else result
