import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop"))
from engine_api import EngineAPI


def test_reset_can_cancel_a_pending_login_without_leaving_engine_busy(tmp_path):
    import json, subprocess

    requests = [
        dict(id=i + 1, method=method, params=params)
        for i, (method, params) in enumerate(
            [
                ("sync", {}),
                ("data.reset", {"confirmation": "초기화"}),
                ("engine.state", {}),
                ("quit", {}),
            ]
        )
    ]
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "desktop/engine_main.py"),
            "--data-dir",
            str(tmp_path),
        ],
        input="".join(json.dumps(row) + "\n" for row in requests),
        text=True,
        capture_output=True,
        encoding="utf-8",
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    messages = [json.loads(line) for line in result.stdout.splitlines()]
    assert next(row for row in messages if row.get("id") == 2)["result"] is True
    assert next(row for row in messages if row.get("id") == 3)["result"] == dict(
        loggedIn=False, busy=False
    )


def test_onboarding_and_home_message_survive_restart(tmp_path):
    api = EngineAPI(tmp_path)
    assert api.bootstrap()["preferences"]["onboarding_complete"] is False
    api.dispatch("onboarding.finish", {"nickname": "클로네", "theme": "purple"})
    api.dispatch("profile.save", {"greeting": "좋은 하루예요, {닉네임}님."})
    api.close()
    reopened = EngineAPI(tmp_path)
    try:
        preferences = reopened.bootstrap()["preferences"]
        assert preferences["nickname"] == "클로네"
        assert preferences["theme"] == "purple"
        assert preferences["greeting"] == "좋은 하루예요, {닉네임}님."
        assert preferences["onboarding_complete"] is True
    finally:
        reopened.close()


@pytest.mark.parametrize("value", ["", "  ", "a" * 31, "이름\n다음", "이름\x00"])
def test_bad_nickname_cannot_complete_setup(tmp_path, value):
    api = EngineAPI(tmp_path)
    try:
        with pytest.raises(ValueError):
            api.dispatch("onboarding.finish", {"nickname": value, "theme": "pink"})
        assert api.bootstrap()["preferences"]["onboarding_complete"] is False
    finally:
        api.close()


def test_reset_needs_confirmation_and_clears_every_account_without_touching_other_files(
    tmp_path,
):
    api = EngineAPI(tmp_path)
    api.activate_account("101")
    api.dispatch("onboarding.finish", {"nickname": "테스트", "theme": "mint"})
    key = api.dispatch(
        "event.add",
        {"title": "보존 확인", "type_id": api.bootstrap()["types"][0]["id"]},
    )
    with pytest.raises(ValueError):
        api.dispatch("data.reset", {"confirmation": "아니요"})
    assert api.event(key).title == "보존 확인"
    api.activate_account("202")
    api.dispatch(
        "event.add",
        {"title": "다른 계정 일정", "type_id": api.bootstrap()["types"][0]["id"]},
    )
    (tmp_path / "private-diary.db").write_bytes(b"synthetic encrypted database")
    (tmp_path / "canvas_session.dpapi").write_bytes(b"synthetic session")
    (tmp_path / "unrelated.txt").write_text("keep", encoding="utf-8")
    api.dispatch("data.reset", {"confirmation": "초기화"})
    try:
        fresh = api.bootstrap()
        assert (
            not fresh["events"]
            and not fresh["courses"]
            and not fresh["tasks"]
            and not fresh["journals"]
        )
        assert fresh["preferences"]["onboarding_complete"] is False
        assert fresh["preferences"]["nickname"] == ""
        assert not (tmp_path / "learning-user-202.db").exists()
        assert not (tmp_path / "private-diary.db").exists()
        assert not (tmp_path / "canvas_session.dpapi").exists()
        assert not list(tmp_path.glob(".calix-reset-*"))
        assert (tmp_path / "unrelated.txt").read_text() == "keep"
    finally:
        api.close()
