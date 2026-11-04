"""Windows CI only: legacy publisher migration and the real frozen update launcher."""

from pathlib import Path
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
import winreg
import psutil

ROOT = Path(__file__).resolve().parents[2]
UNINSTALL = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Calix"
NEW_KEY = r"Software\Lutein Studio\Calix"


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run_installer(executable, arguments, timeout=120):
    # NSIS requires /D= to be last and unquoted, including paths with spaces.
    directory = next((value for value in arguments if value.startswith("/D=")), None)
    command = subprocess.list2cmdline(
        [
            str(executable),
            *[value for value in arguments if not value.startswith("/D=")],
        ]
    )
    if directory:
        command += " " + directory
    process = subprocess.Popen(
        command, executable=str(executable), creationflags=subprocess.CREATE_NO_WINDOW
    )
    try:
        result = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        raise RuntimeError("Installer timed out")
    if result:
        raise RuntimeError(f"Installer exited with {result}")


def installation():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL) as key:
        return Path(winreg.QueryValueEx(key, "InstallLocation")[0].strip('"'))


def main():
    if os.name != "nt" or os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError(
            "Installer registry tests are restricted to disposable Windows CI runners"
        )
    setup = ROOT / "desktop/.build/packages/Calix-1.5.94-Setup-x64.exe"
    expected = ROOT / "desktop/src-tauri/target/release/calix-desktop.exe"
    # NSIS changes the Tauri marker when embedding the UI into its payload.
    expected_ui = expected.read_bytes().replace(
        b"__TAURI_BUNDLE_TYPE_VAR_UNK", b"__TAURI_BUNDLE_TYPE_VAR_NSS"
    )
    with tempfile.TemporaryDirectory(prefix="calix-reinstall-") as folder:
        root = Path(folder).resolve()
        target = root / "한글 폴더" / "Calix installed"
        old = root / "legacy.exe"
        urllib.request.urlretrieve(
            "https://github.com/luttechan/Calix/releases/download/v1.5.8/Calix-1.5.8-Setup-x64.exe",
            old,
        )
        if (
            digest(old)
            != "a896208d69715cf0d6880f602256a17e0c63c3c1dd0b3b72809f17fc90f7a5bc"
        ):
            raise RuntimeError("Legacy installer checksum mismatch")
        run_installer(old, ["/S", "/D=" + str(target)])
        # Reproduce the publisher transition with no new manufacturer key.
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, NEW_KEY)
        except FileNotFoundError:
            pass
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, UNINSTALL, 0, winreg.KEY_SET_VALUE
        ) as key:
            # Same-version passive reinstall exercises the old uninstaller path.
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, "1.5.94")
        data = Path(os.environ["APPDATA"]) / "LutteLaurent/Calix"
        data.mkdir(parents=True, exist_ok=True)
        sentinel = data / "installer-preserve-check.txt"
        sentinel.write_text(
            "Synthetic CI data. Must survive every update.", encoding="utf-8"
        )
        settings = data / "settings.json"
        settings.write_text('{"nickname": "CI fixture"}', encoding="utf-8")
        database = data / "learning.db"
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TABLE preserved (title TEXT)")
            connection.execute("INSERT INTO preserved VALUES ('synthetic schedule')")
        connection.close()
        campus = Path(os.environ["LOCALAPPDATA"]) / "io.github.luttechan.calix" / "campus-session"
        campus.mkdir(parents=True, exist_ok=True)
        profile = campus / "installer-preserve-check.txt"
        profile.write_text("Synthetic campus profile.", encoding="utf-8")
        before = {path: digest(path) for path in (sentinel, settings, database, profile)}
        obsolete_runtime = target / "_internal" / "obsolete" / "legacy.dll"
        obsolete_runtime.parent.mkdir(parents=True)
        obsolete_runtime.write_bytes(b"obsolete runtime fixture")
        unrelated = target / "notes.txt"
        unrelated.write_text("Keep this file.", encoding="utf-8")
        run_installer(setup, ["/P"])
        if obsolete_runtime.exists() or not unrelated.is_file():
            raise RuntimeError("Legacy cleanup did not respect the runtime boundary")
        if (
            installation() != target
            or (target / "calix-desktop.exe").read_bytes() != expected_ui
        ):
            raise RuntimeError("Legacy publisher path was not restored")
        if digest(target / "calix-engine.exe") != digest(
            ROOT / "desktop/.build/dist/calix-engine/calix-engine.exe"
        ):
            raise RuntimeError("Legacy reinstall retained an outdated engine")
        print(
            json.dumps(dict(legacyReinstallPassed=True, installedEngineCurrent=True)),
            flush=True,
        )
        if any(not path.is_file() or digest(path) != checksum for path, checksum in before.items()):
            raise RuntimeError("Setup modified user data")
        # Run the exact packaged --utility install path, including the parent wait
        # and PyInstaller DLL environment, without touching a real user's registry.
        with tempfile.TemporaryDirectory(prefix="Calix-update-") as update_folder:
            update = Path(update_folder).resolve() / "Calix-Setup.exe"
            update.write_bytes(setup.read_bytes())
            parent = subprocess.Popen(
                [sys.executable, "-c", "import time;time.sleep(1)"],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            utility = subprocess.Popen(
                [
                    str(target / "calix-engine.exe"),
                    "--utility",
                    "install",
                    "--installer",
                    str(update),
                    "--digest",
                    digest(update),
                    "--wait-pid",
                    str(parent.pid),
                ],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            launched = None
            deadline = time.monotonic() + 40
            try:
                while time.monotonic() < deadline and launched is None:
                    for candidate in psutil.process_iter(["name"]):
                        try:
                            if (
                                candidate.info.get("name") or ""
                            ).lower() != "calix-setup.exe":
                                continue
                            value = candidate.exe()
                            if value and Path(value).resolve() == update:
                                launched = candidate
                                break
                        except (OSError, psutil.Error):
                            pass
                    if utility.poll() not in (None, 0):
                        raise RuntimeError("Packaged update launcher failed")
                    time.sleep(0.02)
                if launched is None:
                    raise RuntimeError("Packaged launcher did not start Setup")
                if utility.wait(timeout=30) != 0:
                    raise RuntimeError("Packaged launcher did not exit cleanly")
                if launched.wait(timeout=120) != 0:
                    raise RuntimeError("In-app Setup failed")
            finally:
                for process in (parent, utility):
                    if process.poll() is None:
                        process.kill()
                    process.wait()
            app = None
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline and app is None:
                for candidate in psutil.process_iter(["exe"]):
                    try:
                        executable = candidate.info.get("exe")
                        if executable and Path(executable).resolve() == (target / "calix-desktop.exe").resolve():
                            app = candidate
                            break
                    except (OSError, psutil.Error):
                        pass
                if app is None:
                    time.sleep(0.05)
            if app is None:
                raise RuntimeError("Installed Calix did not launch after updating")
            for child in app.children(recursive=True):
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass
            app.terminate()
            app.wait(timeout=20)
            if (
                installation() != target
                or (target / "calix-desktop.exe").read_bytes() != expected_ui
            ):
                raise RuntimeError("In-app same-version reinstall failed")
        for path in (sentinel, settings, profile):
            if not path.is_file() or digest(path) != before[path]:
                raise RuntimeError("Update modified user data")
        with sqlite3.connect(database) as connection:
            if connection.execute("SELECT title FROM preserved").fetchone() != ("synthetic schedule",):
                raise RuntimeError("Update modified the saved schedule")
        connection.close()
    print(
        json.dumps(
            dict(
                passed=True,
                legacyPublisherMigration=True,
                sameVersionReinstall=True,
                unicodeAndSpacePath=True,
                frozenUpdateLauncher=True,
                userDataPreserved=True,
            )
        )
    )


if __name__ == "__main__":
    main()
