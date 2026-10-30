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
    version = (
        (ROOT / "version_info.txt")
        .read_text(encoding="utf-8")
        .replace("1.3.0", "1.4.1")
        .replace("(1,3,0,0)", "(1,4,1,0)")
    )
    (build / "engine_version.txt").write_text(version, encoding="utf-8")
    spec = (ROOT / "Calix.spec").read_text(encoding="utf-8")
    changes = {
        "root = Path(SPECPATH)": f"root = Path({str(ROOT)!r})",
        "product = 'Calix-Debug' if debug else 'Calix'": "product = 'calix-engine'",
        "[str(root / 'main.py')], pathex=[str(root)]": "[str(root/'desktop/engine_main.py')], pathex=[str(root),str(root/'desktop')]",
        "console=debug": "console=True",
        "version=str(root/'version_info.txt')": "version=str(root/'desktop/.build/engine_version.txt')",
        "name=product+' 1.3.0'": "name=product",
    }
    changes[
        "hiddenimports=['learning_calendar.login_browser', 'keyring.backends.Windows']"
    ] = "hiddenimports=[]"
    changes[
        "asset_data=[(str(root/path),str(Path(path).parent)) for path in RUNTIME_ASSETS]"
    ] = "asset_data=[(str(root/path),str(Path(path).parent)) for path in RUNTIME_ASSETS if path.startswith('asset/calendar/')]"
    for before, after in changes.items():
        assert before in spec, before
        spec = spec.replace(before, after)
    spec_path = build / "engine.spec"
    spec_path.write_text(spec, encoding="utf-8")
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
