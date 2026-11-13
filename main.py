"""Source entry point for the React/Tauri desktop. No legacy Qt application."""

from pathlib import Path
import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent
DESKTOP = ROOT / "desktop"


def project_python():
    candidate = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if candidate.is_file() and candidate.resolve() != Path(sys.executable).resolve():
        return str(candidate)
    return None


def check_build_python():
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools/check_runtime_security.py")],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        raise RuntimeError(
            "빌드에는 Python 3.14.10과 최신 OpenSSL이 필요합니다. "
            "Python 업데이트 후 .venv를 갱신하세요.\n" + result.stdout.strip()
        )


def configure_tool_paths():
    """Find installed tools even when the parent app has a stale Windows PATH."""
    if os.name != "nt":
        return
    import winreg

    paths = []
    if os.environ.get("CALIX_NODE"):
        paths.append(str(Path(os.environ["CALIX_NODE"]).resolve().parent))
    paths.append(str(Path(os.environ.get("CARGO_HOME") or Path.home() / ".cargo") / "bin"))
    for hive, key in (
        (winreg.HKEY_CURRENT_USER, r"Environment"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
    ):
        try:
            with winreg.OpenKey(hive, key) as handle:
                value, _ = winreg.QueryValueEx(handle, "Path")
            paths.extend(os.path.expandvars(value).split(os.pathsep))
        except OSError:
            pass
    paths.extend(os.environ.get("PATH", "").split(os.pathsep))
    os.environ["PATH"] = os.pathsep.join(dict.fromkeys(p for p in paths if p))


def native_command():
    configure_tool_paths()
    if not shutil.which("cargo"):
        raise RuntimeError(
            "cargo.exe를 찾지 못했습니다. Rust 설치 경로를 CARGO_HOME 또는 PATH로 지정하세요."
        )
    if not shutil.which("pnpm"):
        raise RuntimeError("Node.js 24와 pnpm 11을 설치하세요.")
    return "pnpm tauri dev"


def prepare():
    for script in ("tools/prepare_assets.py", "desktop/tools/prepare_web_assets.py"):
        subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT, check=True)
    if not (DESKTOP / "node_modules/vite/bin/vite.js").exists():
        subprocess.run(
            "pnpm install --frozen-lockfile", shell=True, cwd=DESKTOP, check=True
        )


def preview(data_dir=None, open_browser=True, smoke_report=None):
    node = os.environ.get("CALIX_NODE") or shutil.which("node")
    if not node:
        raise RuntimeError("Node.js 24가 필요합니다.")
    version = subprocess.check_output([node, "--version"], text=True).strip()
    if int(version.lstrip("v").split(".")[0]) < 24:
        raise RuntimeError(
            "Node.js 24가 필요합니다. CALIX_NODE로 실행 파일을 지정할 수 있습니다."
        )
    prepare()
    token = secrets.token_urlsafe(32)
    env = dict(os.environ, CALIX_DEV_TOKEN=token)
    args = [sys.executable, "-B", str(DESKTOP / "engine_main.py"), "--dev-http", "5174"]
    if data_dir:
        args += ["--data-dir", str(Path(data_dir).resolve())]
    engine = subprocess.Popen(args, cwd=ROOT, env=env)
    vite = None

    def rpc(method):
        request = urllib.request.Request(
            "http://127.0.0.1:5174/api",
            data=json.dumps(dict(id=1, method=method, params={})).encode(),
            headers={"Content-Type": "application/json", "X-Calix-Token": token},
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            return json.load(response)

    try:
        for _ in range(100):
            if engine.poll() is not None:
                raise RuntimeError("일정 서비스를 시작하지 못했습니다.")
            try:
                rpc("engine.state")
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("일정 서비스 응답이 없습니다.")
        vite = subprocess.Popen(
            [
                node,
                str(DESKTOP / "node_modules/vite/bin/vite.js"),
                "--host",
                "127.0.0.1",
                "--port",
                "5173",
                "--strictPort",
            ],
            cwd=DESKTOP,
            env=env,
        )
        for _ in range(100):
            if vite.poll() is not None:
                raise RuntimeError(
                    "React 화면을 시작하지 못했습니다. 5173 포트를 확인하세요."
                )
            try:
                with urllib.request.urlopen(
                    "http://127.0.0.1:5173/", timeout=1
                ) as response:
                    document = response.read().decode("utf-8")
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("React 화면 응답이 없습니다.")
        if smoke_report:
            assert "/src/main.tsx" in document
            version = rpc("bootstrap")["result"]["version"]
            assert version == "1.6.13"
            Path(smoke_report).write_text(
                json.dumps(
                    dict(ui="React", version=version, legacyQt=False, sourceEntry=True)
                ),
                encoding="utf-8",
            )
            return 0
        if open_browser:
            webbrowser.open("http://127.0.0.1:5173/")
        print(
            "React 소스 미리보기: http://127.0.0.1:5173/\n로그인과 설치 기능은 Tauri 앱에서 사용합니다.",
            flush=True,
        )
        return vite.wait()
    finally:
        if vite and vite.poll() is None:
            vite.terminate()
            vite.wait(timeout=5)
        try:
            rpc("quit")
            engine.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            engine.terminate()
            engine.wait(timeout=5)


def main():
    configure_tool_paths()
    parser = argparse.ArgumentParser(description="Calix React/Tauri source launcher")
    parser.add_argument(
        "--preview", action="store_true", help="React source preview without Rust"
    )
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--data-dir")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Show source entry points without opening a window",
    )
    parser.add_argument(
        "--smoke-test", help="Check the live React source entry and engine, then exit"
    )
    args = parser.parse_args()
    if args.check:
        print(
            json.dumps(
                dict(
                    ui="React + TypeScript / Tauri",
                    entry="desktop/src/main.tsx",
                    native="pnpm tauri dev",
                    preview="python main.py --preview",
                    legacyQt=False,
                )
            )
        )
        return 0
    selected = project_python()
    if selected:
        return subprocess.call([selected, str(ROOT / "main.py"), *sys.argv[1:]], cwd=ROOT)
    if args.preview or args.smoke_test:
        return preview(args.data_dir, not args.no_browser, args.smoke_test)
    check_build_python()
    command = native_command()
    prepare()
    # Build from current sources so Python edits are reflected in the sidecar.
    subprocess.run(
        [sys.executable, str(DESKTOP / "tools/build_engine.py")], cwd=ROOT, check=True
    )
    return subprocess.call(command, shell=True, cwd=DESKTOP)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
