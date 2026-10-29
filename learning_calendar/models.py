from __future__ import annotations
from dataclasses import dataclass
import math
from functools import lru_cache
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

KST = ZoneInfo('Asia/Seoul')


@lru_cache(maxsize=8192)
def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(KST)
    except (TypeError, ValueError, OverflowError):
        return None


@dataclass
class Course:
    id: int
    name: str


@dataclass
class Event:
    key: str
    course_id: int
    course_name: str
    kind: str  # movie | assignment
    title: str
    due_at: str | None
    completed: bool
    url: str = ''
    week: str = ''
    starred: bool = False
    note: str = ''
    type_id: int | None = None
    type_name: str = ''
    type_color: str = ''
    manual: bool = False
    series_id: str = ''
    source_title: str = ''
    completion_verified: bool = True

    @property
    def due(self) -> datetime | None:
        return parse_datetime(self.due_at)

    def status(self, now: datetime | None = None) -> str:
        return deadline_display(self, now)[0]

    @property
    def type_label(self):return self.type_name or ('과제' if self.kind=='assignment' else '영상' if self.kind=='movie' else '일정')


def deadline_display(event: Event, now: datetime | None = None) -> tuple[str, str]:
    """A status label and semantic color; completion always takes precedence."""
    if event.kind=='movie' and not event.completion_verified:return ('시청 상태 미확인','neutral')
    if event.completed:
        return ('완료', 'done')
    due = event.due
    if due is None:
        return ('기한 없음', 'neutral')
    now = now or datetime.now(KST)
    seconds = (due - now).total_seconds()
    if seconds <= 0:
        return ('미완료' if event.kind=='assignment' else '기한 경과', 'red')
    if seconds < 3600:
        return (f'마감 {max(1, math.ceil(seconds / 60))}분 전', 'red')
    if seconds < 86400:
        return (f'마감 {math.ceil(seconds / 3600)}시간 전', 'red')
    # Green: more than 7 days, orange: 2-7 days, red: less than 2 days.
    color = 'green' if seconds > 7 * 86400 else ('orange' if seconds >= 2 * 86400 else 'red')
    # Below two days show '1일' instead of a rounded '2일' with a red color.
    days = max(1, int(seconds // 86400))
    return (f'마감 {days}일 전', color)
