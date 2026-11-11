"""Semester settings stored with each account's timetable."""

import json
from datetime import datetime
from .models import KST


def validate(value):
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("terms"), list)
        or not 1 <= len(value["terms"]) <= 100
    ):
        raise ValueError("학기를 확인하세요.")
    names = set()
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
    if type(value.get("confirmed", False)) is not bool:
        raise ValueError("학기 설정을 확인하세요.")
    if value.get("main") not in names:
        raise ValueError("메인 학기를 확인하세요.")
    return value


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


def update(store, operation, name, days=None):
    value = config(store)
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
            store.set_meta(
                "timetable_config", json.dumps(value, ensure_ascii=False), _commit=False
            )
        return name
    if operation == "add":
        value["terms"].append({"name": name, "offDays": []})
    else:
        term = next((t for t in value["terms"] if t["name"] == name), None)
        if term is None:
            raise ValueError("학기를 선택하세요.")
        if operation == "main":
            value["main"] = name
        elif operation == "off":
            term["offDays"] = days
        else:
            raise ValueError("지원하지 않는 요청입니다.")
    store.set_meta("timetable_config", json.dumps(validate(value), ensure_ascii=False))
    return name
