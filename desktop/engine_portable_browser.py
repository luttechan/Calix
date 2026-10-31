"""Hardware-independent settings for the invisible course browser only."""

import os


def configure():
    # Qt Quick/Chromium must not depend on a particular laptop GPU or its driver.
    os.environ["QT_OPENGL"] = "software"
    os.environ["QT_QUICK_BACKEND"] = "software"
    flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").split()
    for flag in (
        "--disable-gpu",
        "--disable-gpu-compositing",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        "--disable-backgrounding-occluded-windows",
    ):
        if flag not in flags:
            flags.append(flag)
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(flags)


def collector_class(report):
    from PySide6.QtWebEngineCore import QWebEnginePage
    from learning_calendar.dom_collector import ScreenCollector
    import time

    class PortableCollector(ScreenCollector):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # A page with no view otherwise remains hidden. Chromium can freeze
            # its scripts on background/power-saving systems.
            self.page.setLifecycleState(QWebEnginePage.LifecycleState.Active)
            self.page.loadFinished.connect(
                lambda ok: report(
                    f"화면 로드 {'완료' if ok else '실패'} {self.page.url().path() if self.page else '종료'}"
                )
            )
            self.page.renderProcessTerminated.connect(
                lambda status, code: report(f"렌더러 종료 {status.name} code={code}")
            )
            self._reported_state = None
            self._ready_signature = None
            self._ready_since = 0

        def next_course(self):
            super().next_course()
            if self.active:
                self.page.setVisible(True)
                self.page.setLifecycleState(QWebEnginePage.LifecycleState.Active)
                self.deadline = time.monotonic() + 60
                self._reported_state = None
                self._ready_signature = None
                self._ready_since = 0

        def observed(self, generation, value):
            import json

            current = value
            if isinstance(current, str):
                try:
                    current = json.loads(current)
                except ValueError:
                    current = None
            if (
                self.active
                and generation == self.generation
                and isinstance(current, dict)
            ):
                state = (
                    self.index,
                    current.get("state"),
                    current.get("weeks"),
                    len(current["items"]) if isinstance(current.get("items"), list) else 0,
                )
                if state != self._reported_state:
                    self._reported_state = state
                    report(
                        f"과목 {self.courses[self.index]['id']} 상태={state[1]} 주차={state[2]} 영상={state[3]}"
                    )
                if current.get("state") == "ready":
                    signature = json.dumps(current, sort_keys=True, ensure_ascii=False)
                    if signature != self._ready_signature:
                        self._ready_signature = signature
                        self._ready_since = time.monotonic()
                    # Week headings can precede the asynchronous item response.
                    # Do not finalize a briefly stable, empty or partial list.
                    quiet = 1 if current.get("items") else 8
                    if time.monotonic() - self._ready_since < quiet:
                        self.waiting = False
                        self.last_state = "settling"
                        return
                else:
                    self._ready_signature = None
            super().observed(generation, value)

    return PortableCollector
