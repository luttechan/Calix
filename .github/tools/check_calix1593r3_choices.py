"""Exercise the published Setup through its Windows installer controls."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import winreg

if os.environ.get("GITHUB_ACTIONS") != "true":
    raise RuntimeError("This test requires an isolated Windows CI runner")

user32 = ctypes.WinDLL("user32", use_last_error=True)
callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
for name, types in {
    "EnumWindows": [callback, wintypes.LPARAM],
    "EnumChildWindows": [wintypes.HWND, callback, wintypes.LPARAM],
    "GetWindowThreadProcessId": [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)],
    "GetDlgCtrlID": [wintypes.HWND],
    "GetClassNameW": [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int],
    "IsWindowVisible": [wintypes.HWND],
    "IsWindowEnabled": [wintypes.HWND],
    "SendMessageW": [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM],
    "PostMessageW": [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM],
}.items():
    getattr(user32, name).argtypes = types
user32.SendMessageW.restype = wintypes.LPARAM

INSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Calix"


def installed():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, INSTALL_KEY) as key:
        return Path(winreg.QueryValueEx(key, "InstallLocation")[0].strip('"')).resolve()


def windows(parent=None):
    handles = []

    @callback
    def collect(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            handles.append(hwnd)
        return True

    if parent is None:
        user32.EnumWindows(collect, 0)
    else:
        user32.EnumChildWindows(parent, collect, 0)
    return handles


def window_pid(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def caption(hwnd):
    buf = ctypes.create_unicode_buffer(512)
    user32.SendMessageW(hwnd, 0x000D, len(buf), ctypes.addressof(buf))
    return buf.value.replace("&", "")


def window_class(hwnd):
    buf = ctypes.create_unicode_buffer(32)
    user32.GetClassNameW(hwnd, buf, len(buf))
    return buf.value


def command(window, control):
    user32.PostMessageW(window, 0x0111, user32.GetDlgCtrlID(control), control)


def choose(setup, selection, expected_data):
    proc = subprocess.Popen([str(setup)])
    wizard = None
    selected = False
    confirmed = selection != "데이터 초기화 · 새로 설치"
    deadline = time.monotonic() + 110
    last_state = []
    try:
        while time.monotonic() < deadline:
            exit_code = proc.poll()
            if exit_code is not None:
                if exit_code or not selected or not confirmed:
                    raise RuntimeError(f"Setup did not complete {selection}: {exit_code}")
                return
            dialogs = [
                hwnd for hwnd in windows()
                if window_pid(hwnd) == proc.pid and window_class(hwnd) == "#32770"
                and user32.IsWindowEnabled(hwnd)
            ]
            for dialog in dialogs:
                buttons = [
                    hwnd for hwnd in windows(dialog)
                    if window_class(hwnd) == "Button" and user32.IsWindowEnabled(hwnd)
                ]
                titles = {caption(hwnd): hwnd for hwnd in buttons}
                last_state = list(titles)
                yes = next((hwnd for hwnd in buttons if user32.GetDlgCtrlID(hwnd) == 6), None)
                if yes and selected and not confirmed:
                    assert expected_data.is_file(), "Data deleted before explicit confirmation"
                    command(dialog, yes)
                    confirmed = True
                    continue
                next_button = next((hwnd for hwnd in buttons if user32.GetDlgCtrlID(hwnd) == 1), None)
                if not next_button:
                    continue
                wizard = dialog
                if selection in titles and not selected:
                    preserve = titles.get("데이터 유지 · 이전 버전 삭제")
                    if preserve and user32.IsWindowEnabled(preserve):
                        assert user32.SendMessageW(preserve, 0x00F0, 0, 0) == 1
                    for title, hwnd in titles.items():
                        if title in ("데이터 유지 · 이전 버전 삭제", "데이터 초기화 · 새로 설치", "이전 버전도 보관"):
                            user32.SendMessageW(hwnd, 0x00F1, int(title == selection), 0)
                    selected = True
                next_caption = caption(next_button)
                if ("설치" in next_caption or "Install" in next_caption) and not selected:
                    raise RuntimeError(f"Setup skipped installation choices: {last_state}")
                if "완료" in next_caption or "Finish" in next_caption:
                    for title, hwnd in titles.items():
                        if "실행" in title or "Run Calix" in title:
                            user32.SendMessageW(hwnd, 0x00F1, 0, 0)
                command(wizard, next_button)
                break
            time.sleep(0.25)
        raise RuntimeError(f"Setup UI timed out for {selection}: {last_state}")
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


setup = Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix="calix-choice-") as folder:
    root = Path(folder).resolve()
    original = root / "Calix old"
    cmd = subprocess.list2cmdline([str(setup), "/S"]) + " /D=" + str(original)
    subprocess.run(cmd, executable=str(setup), check=True, timeout=120)
    assert installed() == original
    data = Path(os.environ["APPDATA"]) / "LutteLaurent/Calix"
    data.mkdir(parents=True, exist_ok=True)
    sentinel = data / "learning.db"
    sentinel.write_bytes(b"synthetic schedule data")
    session = Path(os.environ["LOCALAPPDATA"]) / "io.github.luttechan.calix" / "campus-session"
    session.mkdir(parents=True, exist_ok=True)
    cookie = session / "installer-test.txt"
    cookie.write_bytes(b"synthetic login data")
    obsolete = original / "_internal" / "obsolete.txt"
    obsolete.write_bytes(b"old version file")
    choose(setup, "데이터 유지 · 이전 버전 삭제", sentinel)
    assert installed() == original and not obsolete.exists()
    assert sentinel.read_bytes() == b"synthetic schedule data" and cookie.is_file()
    obsolete.write_bytes(b"old version file")
    choose(setup, "이전 버전도 보관", sentinel)
    sibling = installed()
    assert sibling != original and sibling.parent == root
    assert (original / "calix-desktop.exe").is_file() and obsolete.is_file()
    assert sentinel.read_bytes() == b"synthetic schedule data" and cookie.is_file()
    choose(setup, "데이터 초기화 · 새로 설치", sentinel)
    assert installed() == sibling
    assert data.is_dir() and not sentinel.exists() and not cookie.exists()
    assert (original / "calix-desktop.exe").is_file() and obsolete.is_file()
    print("All three Setup choices verified")
