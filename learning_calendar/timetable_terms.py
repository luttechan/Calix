"""Semester settings stored with each account's timetable."""

import json
from datetime import date, datetime
from .models import KST


def validate(value):
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("terms"), list)
        or not 1 <= len(value["terms"]) <= 100
    ):
        raise ValueError("학기를 확인하세요.")
    names = set()
    periods = []
    for term in value["terms"]:
        if not isinstance(term, dict):
            raise ValueError("학기를 확인하세요.")
        name, days = term.get("name"), term.get("offDays")
        if (
            not isinstance(name, str)
            or not name.strip()
            or name != name.strip()
            or len(name) > 40
            or name in names
        ):
            raise ValueError("학기 이름을 확인하세요.")
        if (
            not isinstance(days, list)
            or len(days) > 7
            or any(type(d) is not int or not 0 <= d < 7 for d in days)
            or len(set(days)) != len(days)
        ):
            raise ValueError("공강 요일을 확인하세요.")
        names.add(name)
        start, end = term.get("startsOn"), term.get("endsOn")
        if start is not None or end is not None:
            if not valid_day(start) or not valid_day(end) or start > end:
                raise ValueError("학기 시작일과 종료일을 확인하세요.")
            periods.append((start, end))
    ordered = sorted(periods)
    if any(previous[1] >= following[0] for previous, following in zip(ordered, ordered[1:])):
        raise ValueError("학기 기간이 겹칩니다.")
    if type(value.get("confirmed", False)) is not bool:
        raise ValueError("학기 설정을 확인하세요.")
    if value.get("main") not in names:
        raise ValueError("메인 학기를 확인하세요.")
    if any(type(value.get(key, default)) is not bool for key, default in (("automatic", False), ("seasonal", True))):
        raise ValueError("자동 학기 전환 설정을 확인하세요.")
    return value


def valid_day(value):
    try:
        return isinstance(value, str) and date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def dated_term(value, day):
    return next((term["name"] for term in value["terms"]
                 if term.get("startsOn") and term["startsOn"] <= day <= term["endsOn"]
                 and (value.get("seasonal", True) or not term["name"].endswith("계절학기"))), None)


def activate_current(store, today=None):
    value = config(store)
    day = (today or datetime.now(KST).date()).isoformat()
    if not value.get("automatic") or dated_term(value, day) in (None, value["main"]):
        return value
    store.db.execute("BEGIN IMMEDIATE")
    with store.db:
        value = config(store)
        target = dated_term(value, day) if value.get("automatic") else None
        if target and target != value["main"]:
            from .grades import anchor_cached_roster

            anchor_cached_roster(store, value["main"])
            value["main"] = target
            write(store, value)
    return value


def write(store, value):
    store.set_meta("timetable_config", json.dumps(validate(value), ensure_ascii=False), _commit=False)


def configure_dates(store, action, params):
    from .academic_calendar import BUFS_PERIODS

    store.db.execute("BEGIN IMMEDIATE")
    with store.db:
        value = config(store)
        if action == "school":
            if not value.get("confirmed", False):
                has_timetable = store.db.execute("SELECT 1 FROM timetable LIMIT 1").fetchone()
                has_grades = store.db.execute("SELECT 1 FROM grade_items LIMIT 1").fetchone()
                if has_timetable or has_grades:
                    raise ValueError("기존 자료가 속한 학기를 먼저 설정하세요.")
                value["confirmed"] = True
            terms = {term["name"]: term for term in value["terms"]}
            for name, (start, end) in BUFS_PERIODS.items():
                if name not in terms:
                    value["terms"].append({"name": name, "offDays": [], "startsOn": start, "endsOn": end})
                elif not terms[name].get("startsOn"):
                    terms[name].update(startsOn=start, endsOn=end)
            value["automatic"] = True
        elif action == "mode":
            for key in ("automatic", "seasonal"):
                if key in params:
                    value[key] = params[key]
        elif action == "dates":
            term = next((term for term in value["terms"] if term["name"] == params.get("name")), None)
            if term is None:
                raise ValueError("학기를 선택하세요.")
            term.update(startsOn=params.get("startsOn"), endsOn=params.get("endsOn"))
        else:
            raise ValueError("지원하지 않는 학기 설정입니다.")
        validate(value)
        if value.get("automatic"):
            target = dated_term(value, datetime.now(KST).date().isoformat())
            if target and target != value["main"]:
                from .grades import anchor_cached_roster

                anchor_cached_roster(store, value["main"])
                value["main"] = target
        write(store, value)
    return value["main"]


def config(store):
    return validate(json.loads(store.get_meta("timetable_config")))


def initialize(store):
    now = datetime.now(KST)
    default = f"{now.year}학년도 {1 if now.month < 8 else 2}학기"
    try:
        value = config(store)
    except (ValueError, TypeError):
        try:
            days = json.loads(store.get_meta("timetable_off_days", "[]"))
            if not isinstance(days, list) or any(
                type(d) is not int or not 0 <= d < 7 for d in days
            ):
                days = []
        except (ValueError, TypeError):
            days = []
        value = {
            "main": default,
            "confirmed": False,
            "terms": [{"name": default, "offDays": sorted(set(days))}],
        }
    names = {t["name"] for t in value["terms"]}
    for row in store.db.execute(
        "SELECT DISTINCT semester FROM timetable WHERE semester<>''"
    ):
        if row[0] not in names:
            value["terms"].append({"name": row[0], "offDays": []})
            names.add(row[0])
    store.db.execute(
        "UPDATE timetable SET semester=? WHERE semester=''", (value["main"],)
    )
    store.set_meta(
        "timetable_config",
        json.dumps(validate(value), ensure_ascii=False),
        _commit=False,
    )


def update(store, operation, name, days=None, *, make_main=False):
    value = config(store)
    previous = value["main"]
    if operation in ("add", "main") and not value.get("confirmed", False):
        raise ValueError("먼저 학기를 설정하세요.")
    if operation == "configure":
        if value.get("confirmed", False):
            raise ValueError("이미 학기가 설정되어 있습니다.")
        old = value["main"]
        days = next(t["offDays"] for t in value["terms"] if t["name"] == old)
        value = {
            "main": name,
            "confirmed": True,
            "terms": [{"name": name, "offDays": days}],
        }
        validate(value)
        with store.db:
            store.db.execute("UPDATE timetable SET semester=?", (name,))
            tables = {row[0] for row in store.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "grade_items" in tables:
                store.db.execute("UPDATE grade_items SET semester=? WHERE semester=?", (name, old))
                store.db.execute("UPDATE grade_scales SET semester=? WHERE semester=?", (name, old))
            from .grades import ROSTERS, course_rosters

            rosters = course_rosters(store)
            if old in rosters:
                rosters[name] = rosters.pop(old)
                store.set_meta(ROSTERS, json.dumps(rosters, ensure_ascii=False), _commit=False)
            store.set_meta(
                "timetable_config", json.dumps(value, ensure_ascii=False), _commit=False
            )
        return name
    if operation == "add":
        value["terms"].append({"name": name, "offDays": []})
        if make_main:
            value.update(main=name, automatic=False)
    else:
        term = next((t for t in value["terms"] if t["name"] == name), None)
        if term is None:
            raise ValueError("학기를 선택하세요.")
        if operation == "main":
            value.update(main=name, automatic=False)
        elif operation == "off":
            term["offDays"] = days
        else:
            raise ValueError("지원하지 않는 요청입니다.")
    with store.db:
        if value["main"] != previous:
            from .grades import anchor_cached_roster

            anchor_cached_roster(store, previous)
        write(store, value)
    return name
