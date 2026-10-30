"""Freeze the existing Python engine as a private stdio sidecar."""

from pathlib import Path
import subprocess, sys, shutil

ROOT = Path(__file__).resolve().parents[2]


def main():
    subprocess.run(
        [sys.executable, str(ROOT / "tools/check_runtime_security.py")], check=True
    )
    subprocess.run(
        [sys.executable, "-B", str(ROOT / "tools/prepare_assets.py")], check=True
    )
    build = ROOT / "desktop/.build"
    build.mkdir(exist_ok=True)
    spec_path = ROOT / "Calix.spec"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(build / "dist"),
            "--workpath",
            str(build / "cache"),
            str(spec_path),
        ],
        cwd=ROOT,
        check=True,
    )
    bundle = build / "dist/calix-engine"
    binaries = ROOT / "desktop/src-tauri/binaries"
    binaries.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        bundle / "calix-engine.exe",
        binaries / "calix-engine-x86_64-pc-windows-msvc.exe",
    )
    resources = ROOT / "desktop/src-tauri/engine"
    resources.mkdir(exist_ok=True)
    internal = resources / "_internal"
    assert internal.resolve().parent == resources.resolve()
    if internal.exists():
        shutil.rmtree(internal)
    shutil.copytree(bundle / "_internal", internal)
    print("Python sidecar ready")


if __name__ == "__main__":
    main()
