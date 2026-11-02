"""One bounded, monotonic focus clock; no worker, polling thread or audio process."""

import time
import uuid
import json
from datetime import datetime, timedelta, time as day_time
from .models import KST


class FocusClock:
    def __init__(self, store):
        self.store = store
        self.running = False
        self.mode = "pomodoro"
        self.phase = "focus"
        self.round = 0
        self.work, self.short, self.long = 25 * 60, 5 * 60, 15 * 60
        self.elapsed = 0.0
        self.mark = time.monotonic()
        self.key = ""
        self.day = ""
        self.credited = {}
        try:
            config = json.loads(store().get_meta("focus_config", "{}"))
            if config.get("mode") in ("free", "pomodoro") and all(
                type(config.get(k)) is int and 1 <= config[k] <= 180
                for k in ("work", "short", "long")
            ):
                self.mode = config["mode"]
                self.work, self.short, self.long = (
                    config[k] * 60 for k in ("work", "short", "long")
                )
        except (ValueError, TypeError, AttributeError):
            pass
        store().db.execute(
            "CREATE TABLE IF NOT EXISTS focus_sessions (id TEXT PRIMARY KEY, day TEXT NOT NULL, seconds INTEGER NOT NULL)"
        )
        store().db.commit()

    def tick(self):
        now = time.monotonic()
        if self.running:
            delta = max(0, now - self.mark)
            if delta > 120:
                # No clock heartbeat means suspension or a stalled process. Do not
                # record the entire sleep interval as study time.
                self.running = False
                self.mark = now
                return
            limit = (
                self.work
                if self.phase == "focus"
                else self.long if self.round % 4 == 0 else self.short
            )
            previous = self.elapsed
            self.elapsed = (
                self.elapsed + delta
                if self.mode == "free"
                else min(limit, self.elapsed + delta)
            )
            if self.mode != "free" and self.elapsed >= limit:
                self.running = False
            if self.phase == "focus" and self.key:
                duration = self.elapsed - previous
                end = datetime.now(KST)
                start = end - timedelta(seconds=duration)
                while start < end:
                    boundary = datetime.combine(
                        start.date() + timedelta(days=1), day_time(), tzinfo=KST
                    )
                    stop = min(boundary, end)
                    day = start.date().isoformat()
                    self.credited[day] = (
                        self.credited.get(day, 0) + (stop - start).total_seconds()
                    )
                    start = stop
                with self.store().db:
                    for day, seconds in self.credited.items():
                        self.store().db.execute(
                            "INSERT INTO focus_sessions VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET seconds=excluded.seconds",
                            (self.key + day, day, int(seconds)),
                        )
        self.mark = now

    def state(self):
        self.tick()
        limit = (
            self.work
            if self.phase == "focus"
            else self.long if self.round % 4 == 0 else self.short
        )
        return dict(
            running=self.running,
            mode=self.mode,
            phase=self.phase,
            round=self.round,
            elapsed=int(self.elapsed),
            duration=limit,
            work=self.work // 60,
            short=self.short // 60,
            long=self.long // 60,
            finished=self.mode != "free" and self.elapsed >= limit,
        )

    def command(self, p):
        action = p.get("action")
        if action not in ("start", "pause", "reset", "next", "configure"):
            raise ValueError("집중 모드 명령을 확인하세요.")
        self.tick()
        if action == "configure":
            if self.running or self.elapsed:
                raise ValueError("현재 세션을 마친 뒤 변경하세요.")
            if p.get("mode") not in ("pomodoro", "free"):
                raise ValueError("집중 모드를 확인하세요.")
            for k in ("work", "short", "long"):
                if type(p.get(k)) is not int or not 1 <= p[k] <= 180:
                    raise ValueError("집중 시간을 확인하세요.")
            self.mode = p["mode"]
            self.work, self.short, self.long = (
                p[k] * 60 for k in ("work", "short", "long")
            )
            self.store().set_meta(
                "focus_config",
                json.dumps({k: p[k] for k in ("mode", "work", "short", "long")}),
            )
        elif action in ("reset", "next"):
            self.running = False
            if action == "next" and self.mode == "pomodoro":
                if self.phase == "focus":
                    self.round += 1
                    self.phase = "break"
                else:
                    self.phase = "focus"
            else:
                self.phase = "focus"
                self.round = 0
            self.elapsed = 0
            self.key = ""
            self.credited = {}
        elif action == "pause":
            self.running = False
        else:
            if self.state()["finished"]:
                raise ValueError("다음 세션을 선택하세요.")
            if not self.key:
                self.key = uuid.uuid4().hex
                self.day = datetime.now(KST).date().isoformat()
            self.running = True
            self.mark = time.monotonic()
        return self.state()

    def totals(self):
        self.tick()
        return [
            dict(row)
            for row in self.store().db.execute(
                "SELECT day,SUM(seconds) seconds FROM focus_sessions GROUP BY day ORDER BY day DESC LIMIT 366"
            )
        ]

    def close(self):
        self.tick()
        self.running = False
