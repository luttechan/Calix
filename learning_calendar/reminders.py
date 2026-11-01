"""Bounded deadline reminders. No background process or network requests."""

import json
from datetime import datetime
from .models import KST, parse_datetime

DEFAULTS = dict(
    enabled=True,
    startup=True,
    sync=True,
    urgent=True,
    urgent_minutes=60,
    general=True,
    general_days=1,
    assignments=True,
    videos=True,
    sound=True,
    track="1",
    volume=0.6,
)


def validate(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULTS):
        raise ValueError("알림 설정을 확인하세요.")
    result = {**DEFAULTS, **value}
    for key in (
        "enabled",
        "startup",
        "sync",
        "urgent",
        "general",
        "assignments",
        "videos",
        "sound",
    ):
        if type(result[key]) is not bool:
            raise ValueError("알림 설정을 확인하세요.")
    for key, low, high in [("urgent_minutes", 1, 10080), ("general_days", 0, 365)]:
        if type(result[key]) is not int or not low <= result[key] <= high:
            raise ValueError("알림 시간을 확인하세요.")
    if not isinstance(result["track"], str) or result["track"] not in {
        str(n) for n in range(1, 11)
    }:
        raise ValueError("알람 음원을 선택하세요.")
    volume = result["volume"]
    if type(volume) not in (int, float) or not 0 <= volume <= 1:
        raise ValueError("음량을 확인하세요.")
    return result


def pending(events, settings, now):
    result = []
    for event in events:
        if (
            event.completed
            or event.kind not in ("assignment", "movie")
            or not event.due_at
        ):
            continue
        if not settings["assignments" if event.kind == "assignment" else "videos"]:
            continue
        due = parse_datetime(event.due_at)
        if due is None:
            continue
        seconds = (due - now).total_seconds()
        if seconds <= 0:
            continue
        stage = None
        if settings["urgent"] and seconds <= settings["urgent_minutes"] * 60:
            stage = "urgent"
        elif settings["general"] and (
            seconds <= settings["general_days"] * 86400
            if settings["general_days"]
            else due.date() == now.date()
        ):
            stage = "general"
        if stage:
            window = settings["urgent_minutes" if stage == "urgent" else "general_days"]
            result.append(
                (event, stage, f"{event.key}|{event.due_at}|{stage}|{window}")
            )
    return sorted(result, key=lambda row: row[0].due_at)


def check(api, trigger, now=None):
    settings = validate(api.settings.get("reminders", {}))
    if not settings["enabled"] or not api.settings.get("onboarding_complete"):
        return None
    now = now or datetime.now(KST)
    rows = pending(api.store.events(), settings, now)
    try:
        history = json.loads(api.store.get_meta("reminder_history", "{}"))
        if not isinstance(history, dict):
            history = {}
    except ValueError:
        history = {}
    history = {
        k: v
        for k, v in history.items()
        if isinstance(k, str)
        and type(v) in (int, float)
        and now.timestamp() - v < 14 * 86400
    }
    seed = trigger == "startup" and not settings["startup"]
    if trigger == "sync" and not settings["sync"]:
        return None
    selected = (
        rows
        if trigger in ("startup", "sync")
        else [row for row in rows if row[2] not in history]
    )
    if not selected:
        return None
    for event, stage, key in selected:
        history[key] = now.timestamp()
        if stage == "urgent":
            # An urgent alert already covers the earlier general threshold.
            history[
                f'{event.key}|{event.due_at}|general|{settings["general_days"]}'
            ] = now.timestamp()
    api.store.set_meta(
        "reminder_history",
        json.dumps(dict(sorted(history.items(), key=lambda pair: pair[1])[-2000:])),
    )
    if seed:
        return None
    urgent = any(stage == "urgent" for _, stage, _ in selected)
    count = {
        kind: sum(event.kind == kind for event, _, _ in selected)
        for kind in ("assignment", "movie")
    }
    today = all(
        parse_datetime(event.due_at).date() == now.date() for event, _, _ in selected
    )
    title = (
        "마감이 얼마 남지 않았어요."
        if urgent
        else "오늘의 할 일이 있어요!" if today else "다가오는 할 일이 있어요!"
    )
    label = "와 ".join(
        f'{"과제" if kind=="assignment" else "영상"} {n}개'
        for kind, n in count.items()
        if n
    )
    return dict(
        title=title,
        message=f"{label}를 확인해 주세요.",
        urgent=urgent,
        theme=api.settings.get("theme", "pink"),
        glass=api.settings.get("glass", True),
        sound=("crit" if urgent else settings["track"]) if settings["sound"] else "",
        volume=settings["volume"],
        total=len(selected),
        events=[
            dict(
                key=e.key,
                title=e.title,
                course_name=e.course_name,
                kind=e.kind,
                due_at=e.due_at,
            )
            for e, _, _ in selected[:50]
        ],
    )
