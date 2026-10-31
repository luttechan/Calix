"""A real hidden Chromium page that becomes ready after the old 15s limit."""

import os
import subprocess
import sys
from pathlib import Path


def test_slow_hidden_course_extracts_all_videos():
    root = Path(__file__).resolve().parents[1]
    script = r"""
import json, sys
from pathlib import Path
sys.path.insert(0, 'desktop')
from engine_portable_browser import configure
configure()
from PySide6.QtCore import QCoreApplication, QEvent, QTimer, QUrl, Qt
QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
from PySide6.QtGui import QGuiApplication
from PySide6.QtWebEngineCore import QWebEngineProfile
from learning_calendar import dom_collector
app = QGuiApplication([])
app.setQuitOnLastWindowClosed(False)
profile = QWebEngineProfile()
fixture = Path('tests/fixtures/learningx_rendered.html').read_text(encoding='utf-8')
class LocalPage(dom_collector.CoursePage):
    def acceptNavigationRequest(self, url, *args):
        return url.scheme() == "data" or super().acceptNavigationRequest(url, *args)
    def setUrl(self, url):
        # No network requests; keep the production same-origin DOM restrictions.
        html = '<script>setTimeout(()=>{document.body.innerHTML=' + json.dumps(fixture) + ';document.querySelectorAll(".xnmb-module_item-outer-wrapper").forEach(e=>e.remove())},16000);setTimeout(()=>{document.body.innerHTML=' + json.dumps(fixture) + '},20000)</script>'
        self.setHtml(html, QUrl('https://canvas.bufs.ac.kr/courses/1/external_tools/49'))
dom_collector.CoursePage = LocalPage
from engine_portable_browser import collector_class
Collector = collector_class(lambda message: None)
collector = Collector(profile, '1', [dict(id=1, name='Course')])

result = []
collector.finished.connect(lambda value: (result.append(value), app.quit()))
QTimer.singleShot(30000, app.quit)
collector.start()
assert collector.page.isVisible()
app.exec()
collector.cancel()
QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
profile.deleteLater()
QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
assert result, 'collector did not finish'
rows = result[0]['results']
assert len(rows) == 1 and 'error' not in rows[0], rows
assert len(rows[0]['snapshot']['items']) == 17, rows
assert rows[0]['snapshot']['weeks'] == 15
print('SLOW_HIDDEN_COURSE_OK')
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", script],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=40,
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
    )
    assert result.returncode == 0, result.stderr[-3000:] + result.stdout[-1000:]
    assert "SLOW_HIDDEN_COURSE_OK" in result.stdout
