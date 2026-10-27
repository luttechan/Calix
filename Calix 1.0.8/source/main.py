"""Calix: readable console errors and per-user diagnostic logs."""
from __future__ import annotations
import time
PROCESS_START=time.perf_counter()

import sys
from learning_calendar.startup_notice import start_notice
STARTUP_NOTICE=start_notice(sys.argv[1:])

def _early_exception(exc_type,exc_value,tb):
    sys.__excepthook__(exc_type,exc_value,tb)
    if STARTUP_NOTICE.active:STARTUP_NOTICE.fail();STARTUP_NOTICE.wait_closed()

sys.excepthook=_early_exception

import logging
import os
import re
import sys
import threading
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path
from learning_calendar.bootstrap import configure_runtime

configure_runtime()
from learning_calendar.app_identity import configure_windows_identity
configure_windows_identity()

# This Qt warning normally means an invalid *description* in a monitor/image
# ICC color profile. It is unrelated to LMS auth. Hide only this category.
os.environ.setdefault('QT_LOGGING_RULES', 'qt.gui.icc.warning=false')

LOG_DIR = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'Calix' / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / 'app.log'

class SecretSafeFormatter(logging.Formatter):
    def format(self, record):
        message = super().format(record)
        for pattern in (
            r'(?i)(authorization\s*:\s*bearer\s+)\S+',
            r'(?i)(xn_api_token[=:]\s*)[^\s;,&]+',
            r'(?i)((?:password|passwd|cookie|sessionid)[=:]\s*)[^\s;,&]+',
        ):
            message = re.sub(pattern, r'\1[숨김]', message)
        return message

logger = logging.getLogger()
logger.setLevel(logging.INFO)
fmt = SecretSafeFormatter('%(asctime)s [%(levelname)s] %(message)s')
for handler in (logging.StreamHandler(sys.stderr), RotatingFileHandler(
        LOG_FILE, maxBytes=1_048_576, backupCount=2, encoding='utf-8')):
    handler.setFormatter(fmt)
    logger.addHandler(handler)


def exception_hook(exc_type, exc_value, tb):
    logger.error('처리되지 않은 오류\n%s', ''.join(traceback.format_exception(exc_type, exc_value, tb)))
    if exc_type not in (KeyboardInterrupt, SystemExit):
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            if QApplication.instance():
                QMessageBox.critical(None, '프로그램 오류',
                    f'{type(exc_value).__name__}: {exc_value}\n\n자세한 기록: {LOG_FILE}')
        except Exception:
            pass

sys.excepthook = exception_hook

def thread_hook(args):
    exception_hook(args.exc_type, args.exc_value, args.exc_traceback)

threading.excepthook = thread_hook


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--login',action='store_true')
    parser.add_argument('--session-output')
    parser.add_argument('--session-input')
    parser.add_argument('--ready-file')
    parser.add_argument('--control-server')
    parser.add_argument('--theme',default='sky')
    parser.add_argument('--demo',action='store_true')
    parser.add_argument('--smoke-test',type=Path)
    parser.add_argument('--connection-check',type=Path)
    parser.add_argument('--startup-check',type=Path)
    parser.add_argument('--startup-items',type=int,default=0)
    parser.add_argument('--memory-check',type=Path)
    parser.add_argument('--navigation-check',type=Path)
    parser.add_argument('--navigation-items',type=int,default=5000)
    args=parser.parse_args()
    if args.connection_check:
        from learning_calendar.diagnostics import check_connection
        return check_connection(args.connection_check)
    if args.login:
        if not args.session_output:parser.error('--session-output is required')
        from learning_calendar.login_browser import run
        return run(args.session_output,args.session_input,args.theme,args.ready_file,args.control_server)
    from PySide6.QtWidgets import QApplication
    from learning_calendar.gui import MainWindow
    from learning_calendar.fonts import apply_korean_font
    if args.smoke_test:
        from PySide6.QtCore import QCoreApplication, Qt
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    from PySide6.QtGui import QPixmapCache
    QPixmapCache.setCacheLimit(4096)
    from learning_calendar.app_identity import apply_app_icon
    apply_app_icon(app)
    app.setStyle('Fusion')
    from learning_calendar.design import apply_palette
    apply_palette(app)
    logger.info('UI 글꼴: %s', apply_korean_font(app))
    app.setApplicationName('Calix')
    app.setOrganizationName('LutteLaurent')
    app.setQuitOnLastWindowClosed(True)
    demo_dir=None
    if args.demo or args.smoke_test or args.startup_check or args.memory_check or args.navigation_check:
        from tempfile import TemporaryDirectory
        demo_dir=TemporaryDirectory(prefix='bufs-preview-')
    if args.startup_check and args.startup_items:
        from learning_calendar.storage import Store
        from learning_calendar.models import Course,Event,KST
        from datetime import datetime,timedelta
        seed=Store(Path(demo_dir.name)/'learning.db');now=datetime.now(KST);rows=[]
        for n in range(min(5000,max(0,args.startup_items))):
            rows.append(Event(f'assignment:1:{n}',1,'검사 과목','assignment',f'검사 일정 {n+1}',(now+timedelta(days=n%60+1)).isoformat(),False))
        seed.apply_batch([Course(1,'검사 과목')],{(1,'assignment'):rows});seed.close()
    w = MainWindow(data_dir=demo_dir.name if demo_dir else None,demo=bool(args.demo or args.smoke_test))
    if args.navigation_check:
        from PySide6.QtCore import Qt
        from learning_calendar.navigation_probe import NavigationProbe
        w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen,True)
        navigation_probe=NavigationProbe(w,args.navigation_check,args.navigation_items)
    from learning_calendar.startup_handoff import StartupHandoff
    w._startup_handoff=StartupHandoff(w,STARTUP_NOTICE)
    if args.startup_check:
        from learning_calendar.diagnostics import StartupProbe
        startup_probe=StartupProbe(w,args.startup_check,PROCESS_START,STARTUP_NOTICE)
    w.show()
    if args.memory_check:
        from learning_calendar.memory_probe import MemoryProbe
        memory_probe=MemoryProbe(w,args.memory_check)
    if args.smoke_test:
        from PySide6.QtCore import QTimer
        from learning_calendar.diagnostics import finish_smoke
        QTimer.singleShot(200,lambda:finish_smoke(w,args.smoke_test))
    logger.info('프로그램 실행')
    try:
        return app.exec()
    finally:
        STARTUP_NOTICE.finish()
        logger.info('프로그램 종료')
        if demo_dir:demo_dir.cleanup()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except SystemExit:
        STARTUP_NOTICE.finish()
        raise
    except BaseException as err:
        if STARTUP_NOTICE.active:
            logger.error('시작 실패\n%s',''.join(traceback.format_exception(type(err),err,err.__traceback__)))
            STARTUP_NOTICE.fail();STARTUP_NOTICE.wait_closed()
        else:exception_hook(type(err), err, err.__traceback__)
        raise SystemExit(1)
