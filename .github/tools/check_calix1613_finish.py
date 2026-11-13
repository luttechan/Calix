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
    "GetWindowLongW": [wintypes.HWND, ctypes.c_int],
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


def close_fixture_app(root):
    env = dict(os.environ, CALIX_FIXTURE_ROOT=str(root) + os.sep)
    subprocess.run(
        ["pwsh", "-NoProfile", "-Command", """
        $root = $env:CALIX_FIXTURE_ROOT
        Get-Process |
          Where-Object { $_.ProcessName -in 'calix-desktop','calix-engine' } |
          Where-Object { $_.Path -and $_.Path.StartsWith($root,[StringComparison]::OrdinalIgnoreCase) } |
          ForEach-Object {
            if (-not $_.HasExited) { Stop-Process -Id $_.Id -Force -ErrorAction Stop }
            if (-not $_.WaitForExit(15000)) { throw 'Fixture app did not exit' }
          }
        exit 0
        """],
        check=True, timeout=30, env=env,
    )


def choose(setup, selection, expected_data, auto_launch=False):
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
                last_state = [
                    caption(hwnd) for hwnd in windows(dialog)
                    if window_class(hwnd) in ("Button", "Static")
                ]
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
                if selected and not auto_launch:
                    for hwnd in buttons:
                        if user32.GetWindowLongW(hwnd, -16) & 0xF in (2, 3, 5, 6):
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
with tempfile.TemporaryDirectory(prefix="calix-finish-", ignore_cleanup_errors=True) as folder:
    root = Path(folder).resolve()
    target = root / "Calix installed"
    cmd = subprocess.list2cmdline([str(setup), "/S"]) + " /D=" + str(target)
    subprocess.run(cmd, executable=str(setup), check=True, timeout=120)
    assert installed() == target
    data = Path(os.environ["APPDATA"]) / "LutteLaurent/Calix"
    data.mkdir(parents=True, exist_ok=True)
    sentinel = data / "installer-check.txt"
    sentinel.write_text("Synthetic test data.", encoding="utf-8")
    try:
        choose(setup, "데이터 유지 · 이전 버전 삭제", sentinel, auto_launch=True)
        subprocess.run(
            ["pwsh", "-NoProfile", "-Command", """
            $exe = $env:CALIX_FIXTURE_EXE
            $label = 'Calix (1.6.13)'
            if ((Get-Item -LiteralPath $exe).VersionInfo.ProductName -cne $label) {
              throw "Unexpected Windows product name: $((Get-Item -LiteralPath $exe).VersionInfo.ProductName)"
            }
            $link = Join-Path ([Environment]::GetFolderPath('Programs')) "$label.lnk"
            if (-not (Test-Path -LiteralPath $link)) { throw 'Versioned Start menu shortcut missing' }
            $shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($link)
            if ($shortcut.TargetPath -ne $exe) { throw 'Start menu shortcut points to the wrong executable' }
            $deadline = [DateTime]::UtcNow.AddSeconds(45)
            do {
              $app = Get-Process -Name calix-desktop -ErrorAction SilentlyContinue |
                Where-Object { $_.Path -eq $exe -and $_.MainWindowTitle -ceq $label } |
                Select-Object -First 1
              if ($app) { Write-Host $app.MainWindowTitle; exit 0 }
              Start-Sleep -Milliseconds 250
            } while ([DateTime]::UtcNow -lt $deadline)
            throw 'Setup did not launch Calix with the versioned taskbar window title'
            """],
            env=dict(os.environ, CALIX_FIXTURE_EXE=str(target / "calix-desktop.exe")),
            timeout=55, check=True,
        )
        assert sentinel.read_text(encoding="utf-8") == "Synthetic test data."
    finally:
        close_fixture_app(root)

    import hashlib
    import json
    password = "Installer preservation fixture 160!"
    def exchange(requests):
        result = subprocess.run(
            [str(target / "calix-engine.exe"), "--data-dir", str(data)],
            input="".join(json.dumps(request) + "\n" for request in requests),
            text=True, encoding="utf-8", capture_output=True, timeout=45,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        assert result.returncode == 0, result.stderr
        values = [json.loads(line) for line in result.stdout.splitlines()]
        assert not any(value.get("error") for value in values), values
        return {value["id"]: value["result"] for value in values if "id" in value}
    exchange([
        dict(id=1, method="security.setup", params=dict(password=password, policy=dict(main=True,timetable=True,grades=True,idle_minutes=5))),
        dict(id=2, method="security.unlock", params=dict(password=password, scope="grades")),
        dict(id=3, method="grades.save", params=dict(title="Preserved encrypted course", credits=3, grade="A+")),
        dict(id=4, method="quit", params={}),
    ])
    encrypted_files = [data / "app-lock.json", *data.glob("*.db")]
    before = {path:hashlib.sha256(path.read_bytes()).hexdigest() for path in encrypted_files}
    assert not (data / "learning.db").read_bytes().startswith(b"SQLite format 3")
    try:
        subprocess.run([str(setup), "/P", "/UPDATE"], check=True, timeout=120)
        time.sleep(2)
    finally:
        close_fixture_app(root)
    assert all(hashlib.sha256(path.read_bytes()).hexdigest() == digest for path, digest in before.items())
    results = exchange([
        dict(id=1, method="bootstrap", params={}),
        dict(id=2, method="security.unlock", params=dict(password=password, scope="grades")),
        dict(id=3, method="grades.read", params={}),
        dict(id=4, method="quit", params={}),
    ])
    assert results[1]["security"]["locked"]
    assert results[3]["summary"]["gpa"] == "4.50"
    print("Setup launch, Windows names, encrypted profile and password preservation passed")

