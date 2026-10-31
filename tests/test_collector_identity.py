import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "desktop"))
from engine_portable_browser import collector_class


@pytest.fixture
def collector(monkeypatch):
    from learning_calendar import dom_collector
    import time

    clock = [100.0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])

    class Base:
        def __init__(self):
            self.active = True
            self.generation = 1
            self.index = 0
            self.owner = "7"
            self.courses = [dict(id=2)]
            self.waiting = True
            self.last = "old"
            self.stable = 2
            self.seen = []
            self.page = SimpleNamespace(
                setLifecycleState=lambda value: None,
                loadFinished=SimpleNamespace(connect=lambda callback: None),
                renderProcessTerminated=SimpleNamespace(connect=lambda callback: None),
            )

        def observed(self, generation, value):
            self.seen.append(value)

    monkeypatch.setattr(dom_collector, "ScreenCollector", Base)
    logs = []
    return collector_class(logs.append)(), logs, clock


@pytest.mark.parametrize(
    "override", [dict(course_id=1), dict(owner="8"), dict(items=None)]
)
def test_previous_course_and_other_account_are_not_logged_or_accepted(
    collector, override
):
    instance, logs, clock = collector
    value = dict(state="ready", course_id=2, owner="7", weeks=15, items=[{}])
    value.update(override)
    instance.observed(1, value)
    assert not logs and not instance.seen
    assert instance._ready_signature is None and instance.stable == 0


def test_loading_breaks_previous_stability_streak(collector):
    instance, logs, clock = collector
    instance.observed(1, dict(state="loading"))
    assert instance.last is None and instance.stable == 0


def test_empty_list_can_be_replaced_before_it_is_finalized(collector):
    instance, logs, clock = collector
    value = dict(state="ready", course_id=2, owner="7", weeks=15, items=[])
    instance.observed(1, value)
    clock[0] += 4
    instance.observed(1, value)
    assert not instance.seen
    value = dict(value, items=[dict(title="late video")])
    instance.observed(1, value)
    clock[0] += 1.1
    instance.observed(1, value)
    assert instance.seen == [value]
