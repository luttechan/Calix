"""Offline check for the exact hidden browser used by course collection."""

import json
from pathlib import Path


def run(output):
    from engine_portable_browser import configure
    configure()
    from PySide6.QtCore import QCoreApplication, QEvent, QTimer, Qt

    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
    from PySide6.QtNetwork import QSslSocket

    app = QGuiApplication([])
    app.setQuitOnLastWindowClosed(False)
    profile = QWebEngineProfile()
    page = QWebEnginePage(profile)
    result = dict(passed=False)

    def checked(value):
        result.update(
            passed=value == 42,
            rendered_value=value,
            qt_tls_backend=QSslSocket.activeBackend(),
        )
        app.quit()

    page.loadFinished.connect(
        lambda success: (
            page.runJavaScript(
                "Number(document.getElementById('answer').textContent)", checked
            )
            if success
            else app.quit()
        )
    )
    QTimer.singleShot(10000, app.quit)
    page.setHtml('<!doctype html><div id="answer">42</div>')
    page.setVisible(True)
    app.exec()
    page.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    profile.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    Path(output).write_text(json.dumps(result), encoding="utf-8")
    return 0 if result["passed"] else 2
