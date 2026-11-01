"""Development artifacts only; this command never publishes a release."""

from pathlib import Path
import shutil, zipfile, hashlib, json

ROOT = Path(__file__).resolve().parents[2]


def main():
    desktop = ROOT / "desktop"
    release = desktop / "src-tauri/target/release"
    output = desktop / ".build/packages"
    output.mkdir(parents=True, exist_ok=True)
    exe = release / "calix-desktop.exe"
    assert exe.is_file()
    config = json.loads((desktop / "src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
    version = config["version"]
    assert version == json.loads((desktop / "package.json").read_text(encoding="utf-8"))["version"]
    setup = release / "bundle/nsis" / f"{config['productName']}_{version}_x64-setup.exe"
    assert setup.is_file(), f"Current installer missing: {setup.name}"
    print(json.dumps(dict(selected_installer=setup.name,available_installers=sorted(p.name for p in setup.parent.glob("*setup.exe")))))
    setup_output = output / "Calix-1.5.0-Setup-x64.exe"
    shutil.copy2(setup, setup_output)
    archive = output / "Calix-1.5.0-Windows-x64.zip"
    with zipfile.ZipFile(
        archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=5
    ) as z:
        z.write(exe, "Calix 1.5.0/Calix.exe")
        z.write(
            desktop / "src-tauri/binaries/calix-engine-x86_64-pc-windows-msvc.exe",
            "Calix 1.5.0/calix-engine.exe",
        )
        internal = desktop / "src-tauri/engine/_internal"
        assert not any(path.name.lower() == "qtwebengineprocess.exe" for path in internal.rglob("*.exe")), "Legacy Qt video browser is still bundled"
        for path in internal.rglob("*"):
            if path.is_file():
                z.write(
                    path,
                    "Calix 1.5.0/_internal/" + path.relative_to(internal).as_posix(),
                )
        z.write(ROOT / "LICENSE", "Calix 1.5.0/LICENSE")
        z.write(
            ROOT / "asset/style/Pretendard-OFL.txt", "Calix 1.5.0/Pretendard-OFL.txt"
        )
        z.writestr(
            "Calix 1.5.0/run.bat",
            '@echo off\r\nstart "" /D "%~dp0" "%~dp0Calix.exe"\r\n',
        )
    hashes = []
    for path in (archive, setup_output):
        with path.open("rb") as stream:
            hashes.append(
                f'{hashlib.file_digest(stream,"sha256").hexdigest()}  {path.name}'
            )
    (output / "SHA256SUMS.txt").write_text("\n".join(hashes) + "\n", encoding="utf-8")
    print(
        json.dumps(dict(artifacts=[archive.name, setup_output.name], published=False))
    )


if __name__ == "__main__":
    main()
