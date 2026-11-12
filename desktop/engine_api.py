"""Narrow data API for the desktop UI. No web server or Qt Widgets dependency."""

from pathlib import Path
from dataclasses import asdict
from datetime import datetime
import json
from learning_calendar import secure_db as sqlite3
from learning_calendar.storage import Store
from learning_calendar.models import KST
from learning_calendar.checklist_store import ChecklistStore
from learning_calendar.diary_store import DiaryStore
from learning_calendar.preferences import read_settings, write_settings
from learning_calendar.holidays import HolidayCalendar


class EngineAPI:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        from learning_calendar.app_security import AppSecurity
        self.security = AppSecurity(self.folder)
        self._open_stores()

    def _open_stores(self):
        locked = self.security.state()["locked"]
        destination = lambda name: ":memory:" if locked else self.folder / name
        self.settings_path = self.folder / "settings.json"
        self.settings = read_settings(self.settings_path)
        name = self.settings.get("active_db", "learning.db")
        if (
            not isinstance(name, str)
            or Path(name).name != name
            or not name.endswith(".db")
        ):
            name = "learning.db"
        self.store = Store(destination(name))
        from learning_calendar.grades import initialize
        initialize(self.store)
        self.checklist = ChecklistStore(self.store)
        self.checklist.freeze_imports(self.store.events())
        self.diary = DiaryStore(destination("journals.db"))
        self.vault = None
        from learning_calendar.focus import FocusClock

        self.focus = FocusClock(lambda: self.store)
        self.holidays = HolidayCalendar(destination("holidays.db"))

    def close(self):
        self._close_stores()
        self.security.close()

    def _close_stores(self):
        self.focus.close()
        if self.vault:
            self.vault.close()
        self.diary.close()
        self.holidays.close()
        self.store.close()

    def switch_store(self, path):
        path = Path(path).resolve()
        if path.parent != self.folder.resolve() or not path.name.endswith(".db"):
            raise ValueError("계정 저장소를 확인하세요.")
        candidate = Store(path)
        from learning_calendar.grades import initialize
        initialize(candidate)
        try:
            checklist = ChecklistStore(candidate)
            checklist.freeze_imports(candidate.events())
            settings = dict(self.settings, active_db=path.name)
            write_settings(self.settings_path, settings)
        except Exception:
            candidate.close()
            raise
        changed_account = self.store.path.resolve() != candidate.path.resolve()
        if changed_account:
            self.focus.close()
        self.store.close()
        self.store, self.checklist, self.settings = candidate, checklist, settings
        if changed_account:
            from learning_calendar.focus import FocusClock

            self.focus = FocusClock(lambda: self.store)

    def activate_account(self, owner):
        if (
            not isinstance(owner, str)
            or not owner.isascii()
            or not owner.isdigit()
            or not 0 < int(owner) < 2**63
        ):
            raise ValueError("학교 계정을 확인하세요.")
        current = self.store.get_meta("canvas_user_id")
        if current in ("", owner):
            self.store.set_meta("canvas_user_id", owner)
            return False
        target = self.folder / f"learning-user-{owner}.db"
        original = self.folder / "learning.db"
        if original.exists() and original != self.store.path:
            candidate = Store(original)
            try:
                if candidate.get_meta("canvas_user_id") == owner:
                    target = original
            finally:
                candidate.close()
        candidate = Store(target)
        try:
            if candidate.get_meta("canvas_user_id") not in ("", owner):
                raise ValueError("계정별 저장 파일을 확인하세요.")
        finally:
            candidate.close()
        self.switch_store(target)
        self.store.set_meta("canvas_user_id", owner)
        return True

    def bootstrap(self):
        state = self.security.state()
        if state["locked"]:
            return dict(
                version="1.6.11", events=[], courses=[], types=[], sessions=[],
                timetableTerms=[], mainTerm="", timetableConfigured=False,
                sections=[], statuses=[], tasks=[], offDays=[], journals=[],
                holidays={}, specialDates={}, lastSync="", syncSummary="",
                security=state,
                preferences=dict(theme=self.settings.get("theme", "pink"), glass=True,
                                 reminders={}, nickname="", greeting="{닉네임}님, 오셨군요!",
                                 onboarding_complete=True, attendance_visible=False, attendance_sync=False,
                                 developer_mode=False, font_mode=self.settings.get("font_mode", "pretendard"),
                                 catholic=False, birthday=False, avatar=""),
            )
        events = self.store.events()
        year = datetime.now(KST).year
        return dict(
            version="1.6.11",
            events=[asdict(e) for e in events],
            courses=[asdict(c) for c in self.store.courses()],
            types=self.store.event_types(),
            security=state,
            sessions=[] if self.security.material and self.security.policy["timetable"] and "timetable" not in self.security.scopes else self.store.timetable(all_terms=True),
            timetableTerms=self.store.timetable_config()["terms"],
            mainTerm=self.store.timetable_config()["main"],
            timetableConfigured=self.store.timetable_config().get("confirmed", False),
            sections=self.checklist.sections(),
            statuses=self.checklist.statuses(),
            tasks=[
                row
                for section in self.checklist.sections()
                for row in self.checklist.rows(
                    section["id"], events, self.store.timetable()
                )
            ],
            offDays=self._off_days(),
            preferences=dict(
                {
                    k: self.settings.get(k, d)
                    for k, d in [
                        ("theme", "pink"),
                        ("reminders", {}),
                        ("attendance_visible", False),
                        ("attendance_sync", False),
                        ("glass", True),
                        ("developer_mode", False),
                        ("font_mode", "pretendard"),
                        ("nickname", ""),
                        ("avatar", ""),
                        ("greeting", "{닉네임}님, 오셨군요!"),
                        ("onboarding_complete", False),
                    ]
                },
                catholic=self.holidays.catholic_enabled,
                birthday=self.holidays.birthday_enabled,
            ),
            lastSync=self.store.get_meta("last_sync"),
            syncSummary=self.store.get_meta("sync_summary"),
            holidays={
                day.isoformat(): name
                for y in (year, year + 1)
                for day, name in self.holidays.year(y).items()
            },
            specialDates={
                day.isoformat(): name
                for y in (year, year + 1)
                for day, name in self.holidays.special_dates(y).items()
            },
            journals=self.diary.summaries(),
        )

    def _off_days(self):
        config = self.store.timetable_config()
        return next(
            t["offDays"] for t in config["terms"] if t["name"] == config["main"]
        )

    def event(self, key):
        value = next((e for e in self.store.events() if e.key == key), None)
        if value is None:
            raise ValueError("일정을 찾지 못했습니다.")
        return value

    def task(self, key):
        for section in self.checklist.sections():
            row = next(
                (
                    r
                    for r in self.checklist.rows(
                        section["id"], self.store.events(), self.store.timetable()
                    )
                    if r["id"] == key
                ),
                None,
            )
            if row:
                return row
        raise ValueError("할 일을 찾지 못했습니다.")

    def _diary(self, secret):
        if not secret:
            return self.diary
        if self.vault is None:
            from learning_calendar.diary_crypto import Vault

            self.vault = Vault(self.folder / "private-diary.db")
        return self.vault

    def dispatch(self, method, p):
        if not isinstance(method, str) or not isinstance(p, dict):
            raise ValueError("요청을 확인하세요.")
        self.security.require(method)
        if method.startswith("security."):
            if method == "security.state":
                return self.security.state()
            if method == "security.activity":
                if not self.security.expired():
                    import time
                    self.security.activity = time.monotonic()
                return self.security.state()
            if method == "security.setup":
                policy = self.security.validate(p.get("policy"))
                self._close_stores()
                try:
                    self.security.initialize(p.get("password"), policy)
                finally:
                    self._open_stores()
            elif method == "security.unlock":
                was_cold = self.security.key is None
                self.security.unlock(p.get("password"), p.get("scope", "main"))
                if was_cold:
                    self._close_stores()
                    self._open_stores()
            elif method == "security.configure":
                self.security.configure(p.get("password"), p.get("policy"), p.get("replacement"))
            elif method == "security.lock":
                self.security.lock(p.get("scope", "main"))
            else:
                raise ValueError("잠금 요청을 확인하세요.")
            return self.security.state()
        if method.startswith("grades."):
            from learning_calendar.grades import dispatch
            return dispatch(self.store, method, p)
        if method == "attendance.read":
            from learning_calendar.attendance import read

            return read(self.store)
        if method == "focus.state":
            return self.focus.state()
        if method == "focus.command":
            return self.focus.command(p)
        if method == "focus.totals":
            return self.focus.totals()
        if method == "bootstrap":
            return self.bootstrap()
        if method in ("profile.save", "onboarding.finish"):
            nickname = p.get("nickname", self.settings.get("nickname", ""))
            greeting = p.get(
                "greeting", self.settings.get("greeting", "{닉네임}님, 오셨군요!")
            )
            theme = p.get("theme", self.settings.get("theme", "pink"))
            for value, limit in ((nickname, 30), (greeting, 120)):
                if (
                    not isinstance(value, str)
                    or not 0 < len(value.strip()) <= limit
                    or any(ord(c) < 32 and c != "\n" for c in value)
                ):
                    raise ValueError("닉네임과 홈 문구를 확인하세요.")
            if "\n" in nickname or theme not in (
                "pink",
                "sky",
                "mint",
                "purple",
                "dark",
            ):
                raise ValueError("닉네임과 테마를 확인하세요.")
            from learning_calendar.avatar import validate_avatar

            avatar = validate_avatar(p.get("avatar", self.settings.get("avatar", "")))
            settings = dict(
                self.settings,
                avatar=avatar,
                nickname=nickname.strip(),
                greeting=greeting.strip(),
                theme=theme,
            )
            if method == "onboarding.finish":
                settings["onboarding_complete"] = True
            write_settings(self.settings_path, settings)
            self.settings = settings
            return True
        if method == "data.reset":
            if p.get("confirmation") != "초기화":
                raise ValueError("초기화 확인이 필요합니다.")
            from engine_reset import reset_data

            reset_data(self)
            return True
        if method in ("backup.export", "backup.restore"):
            from learning_calendar.local_backup import (
                write_backup,
                read_backup,
                restore_backup,
            )
            from datetime import datetime

            raw = p.get("path")
            if (
                not isinstance(raw, str)
                or len(raw) > 4096
                or not Path(raw).is_absolute()
                or Path(raw).suffix.lower() != ".calix"
            ):
                raise ValueError("백업 파일을 선택하세요.")
            path = Path(raw)
            if method == "backup.restore" and not self.security.material:
                with path.open("rb") as stream:
                    protected = stream.read(25).startswith(b"Calix password backup v1")
                if protected:
                    raise ValueError("먼저 앱 비밀번호를 설정한 뒤 암호화 백업을 복원하세요.")
            if self.vault:
                self.vault.close()
                self.vault = None
            self.focus.tick()
            if method == "backup.export":
                write_backup(path, self.store, self.folder)
            else:
                value = read_backup(path, self.store.get_meta("canvas_user_id"), p.get("password"))
                recovery = self.folder / (
                    "recovery-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".calix"
                )
                write_backup(recovery, self.store, self.folder)
                self.focus.close()
                restore_backup(value, self.store, self.folder)
                from learning_calendar.focus import FocusClock

                self.focus = FocusClock(lambda: self.store)
                self.holidays.reload()
            return True
        if method == "event.save":
            e = self.event(p["key"])
            if e.manual:
                self.store.save_manual_event(
                    p["title"],
                    p.get("type_id", e.type_id),
                    p.get("due_at", e.due_at),
                    p.get("course_id", e.course_id),
                    p.get("note", ""),
                    e.completed,
                    e.key,
                )
            else:
                self.store.save_event_details(
                    e.key, p["title"], p.get("type_id", e.type_id), p.get("note", "")
                )
            return asdict(self.event(e.key))
        if method == "event.complete":
            e = self.event(p["key"])
            if not e.manual:
                raise ValueError("학교 일정의 완료 상태는 동기화로 확인합니다.")
            if type(p["completed"]) is not bool:
                raise ValueError("완료 상태를 확인하세요.")
            self.store.complete_manual_event(e.key, p["completed"])
            return True
        if method == "event.add":
            return self.store.save_manual_event(
                p["title"],
                p["type_id"],
                p.get("due_at"),
                p.get("course_id", 0),
                p.get("note", ""),
            )
        if method == "event.delete":
            e = self.event(p["key"])
            if not e.manual:
                raise ValueError("학교 일정은 삭제할 수 없습니다.")
            self.store.remove_manual_event(e.key)
            return True
        if method == "type.save":
            return self.store.save_event_type(p["name"], p["color"], p.get("id"))
        if method == "type.delete":
            self.store.remove_event_type(p["id"])
            return True
        if method == "checklist.import":
            keys = p.get("keys", [])
            if (
                not isinstance(keys, list)
                or len(keys) > 20000
                or any(not isinstance(k, str) for k in keys)
            ):
                raise ValueError("일정을 선택하세요.")
            available = {e.key: e for e in self.store.events()}
            return self.checklist.import_events(
                [available[k] for k in dict.fromkeys(keys) if k in available]
            )
        if method == "checklist.add":
            return self.checklist.add(
                p.get("section_id", 1), p.get("title", "새 할 일")
            )
        if method == "checklist.save":
            self.checklist.save(self.task(p["id"]), p["field"], p["value"])
            return True
        if method == "checklist.toggle":
            if type(p["checked"]) is not bool:
                raise ValueError("완료 상태를 확인하세요.")
            self.checklist.toggle(self.task(p["id"]), p["checked"])
            return True
        if method == "checklist.delete":
            self.checklist.trash([self.task(p["id"])])
            return True
        if method == "section.save":
            return self.checklist.save_section(p["name"], p.get("id"))
        if method == "section.delete":
            self.checklist.delete_section(p["id"])
            return True
        if method == "status.save":
            return self.checklist.save_status(
                p["name"], p["color"], p.get("kind", "open"), p.get("id")
            )
        if method == "status.delete":
            self.checklist.delete_status(p["id"])
            return True
        if method == "timetable.save":
            if "slots" in p and not p.get("is_online", False):
                return self.store.add_timetable_slots(p, p["slots"], p.get("id"))
            return self.store.add_timetable(
                p["course_id"],
                p.get("day", 0),
                p.get("start_time", ""),
                p.get("end_time", ""),
                p.get("professor", ""),
                p.get("room", ""),
                p.get("id"),
                color=p.get("color", ""),
                title=p.get("title", ""),
                is_online=p.get("is_online", False),
                semester=p.get("semester"),
            )
        if method == "timetable.delete":
            self.store.remove_timetable(p["id"])
            return True
        if method in (
            "timetable.term.add",
            "timetable.term.main",
            "timetable.term.configure",
        ):
            from learning_calendar.timetable_terms import update

            year, term = p.get("year"), p.get("term")
            if not method.endswith("main"):
                if (
                    type(year) is not int
                    or not 1900 <= year <= 2200
                    or not (
                        (type(term) is int and term in (1, 2))
                        or (type(term) is str and term in ("여름", "겨울"))
                    )
                ):
                    raise ValueError("학년도와 학기를 확인하세요.")
                name = (
                    f"{year}학년도 {term}학기"
                    if type(term) is int
                    else f"{year}학년도 {term} 계절학기"
                )
            else:
                name = p["name"]
            return update(self.store, method.rsplit(".", 1)[1], name)
        if method == "timetable.off":
            days = p["days"]
            if not isinstance(days, list) or any(
                type(day) is not int or not 0 <= day < 7 for day in days
            ):
                raise ValueError("요일을 확인하세요.")
            from learning_calendar.timetable_terms import update

            update(
                self.store,
                "off",
                p.get("semester") or self.store.timetable_config()["main"],
                sorted(set(days)),
            )
            return True
        if method == "diary.list":
            return self._diary(p.get("secret", False)).summaries()
        if method == "diary.read":
            return self._diary(p.get("secret", False)).read(p["id"])
        if method == "diary.save":
            return self._diary(p.get("secret", False)).save(p["value"], p.get("id"))
        if method == "diary.delete":
            self._diary(p.get("secret", False)).remove(p["id"])
            return True
        if method == "vault.state":
            vault = self._diary(True)
            return dict(initialized=vault.initialized, unlocked=vault.unlocked)
        if method == "vault.unlock":
            from learning_calendar.diary_crypto import new_material, unlock_material

            vault = self._diary(True)
            password = p.get("password", "")
            if not isinstance(password, str) or not 1 <= len(password) <= 4096:
                raise ValueError("암호를 확인하세요.")
            if vault.initialized:
                vault.activate(unlock_material(vault.header(), password))
            else:
                if len(password) < 12:
                    raise ValueError("암호는 12자 이상으로 정하세요.")
                key, header = new_material(password)
                vault.initialize(key, header)
            return True
        if method == "vault.lock":
            if self.vault:
                self.vault.lock()
            return True
        if method == "reminders.save":
            from learning_calendar.reminders import validate

            settings = validate(p)
            self.settings["reminders"] = settings
            write_settings(self.settings_path, self.settings)
            return settings
        if method == "preferences.save":
            developer_mode = p.get(
                "developer_mode", self.settings.get("developer_mode", False)
            )
            if type(developer_mode) is not bool:
                raise ValueError("Developer Mode must be a boolean.")
            if (
                developer_mode
                and "developer_mode" in p
                and p.get("developer_acknowledged") is not True
            ):
                raise ValueError("Acknowledge the Developer Mode warning first.")
            theme = p.get("theme", self.settings.get("theme", "pink"))
            glass = p.get("glass", self.settings.get("glass", True))
            mode = p.get("font_mode", self.settings.get("font_mode", "pretendard"))
            if (
                theme not in ("pink", "sky", "mint", "purple", "dark")
                or type(glass) is not bool
                or mode not in ("pretendard", "windows")
            ):
                raise ValueError("테마를 확인하세요.")
            menu_settings = {
                key: p.get(key, self.settings.get(key, False))
                for key in ("attendance_visible", "attendance_sync")
            }
            if any(type(value) is not bool for value in menu_settings.values()):
                raise ValueError("메뉴 활성화 설정을 확인하세요.")
            self.settings.update(
                **menu_settings,
                theme=theme,
                glass=glass,
                font_mode=mode,
                developer_mode=developer_mode,
                developer_acknowledged=developer_mode
                and (
                    p.get("developer_acknowledged") is True
                    or self.settings.get("developer_acknowledged") is True
                ),
            )
            write_settings(self.settings_path, self.settings)
            return True
        if method == "holiday.save":
            self.holidays.save(p["date"], p["name"], p.get("enabled", True))
            return True
        if method == "holiday.reset":
            self.holidays.reset(p["date"])
            return True
        if method == "calendar.year":
            year = p.get("year")
            if type(year) is not int or not 1900 <= year <= 9998:
                raise ValueError("연도를 확인하세요.")
            return dict(
                holidays={
                    day.isoformat(): name
                    for y in (year - 1, year, year + 1)
                    for day, name in self.holidays.year(y).items()
                },
                specialDates={
                    day.isoformat(): name
                    for y in (year - 1, year, year + 1)
                    for day, name in self.holidays.special_dates(y).items()
                },
            )
        if method == "special.save":
            if (
                type(p.get("catholic")) is not bool
                or type(p.get("birthday")) is not bool
            ):
                raise ValueError("일정 설정을 확인하세요.")
            self.holidays.set_catholic(p["catholic"])
            self.holidays.set_birthday(p["birthday"])
            return True
        raise ValueError("지원하지 않는 요청입니다.")
