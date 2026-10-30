"""Check frozen source identity and a real packaged stdio round trip."""

from pathlib import Path
import sys, types, marshal, json, subprocess, tempfile, hashlib
from PyInstaller.archive.readers import CArchiveReader

ROOT = Path(__file__).resolve().parents[2]


def signature(value):
    if isinstance(value, types.CodeType):
        return (
            value.co_code,
            value.co_names,
            value.co_varnames,
            tuple(signature(x) for x in value.co_consts),
        )
    return value


def check(exe):
    exe = Path(exe)
    archive = CArchiveReader(str(exe))
    pyz = archive.open_embedded_archive(
        next(n for n in archive.toc if n.lower().endswith(".pyz"))
    )
    modules = []
    for name in pyz.toc:
        if name == "learning_calendar":
            path = ROOT / "learning_calendar/__init__.py"
        elif name.startswith("learning_calendar."):
            path = ROOT / (name.replace(".", "/") + ".py")
        elif name.startswith("engine_"):
            path = ROOT / "desktop" / (name + ".py")
        else:
            continue
        assert path.is_file(), name
        assert signature(pyz.extract(name)) == signature(
            compile(path.read_bytes(), str(path), "exec")
        ), name
        modules.append(name)
    for required in (
        "engine_api",
        "engine_utility",
        "engine_runtime",
        "engine_sessions",
        "engine_transport",
        "engine_updates",
        "engine_collector",
        "learning_calendar.dom_videos",
        "learning_calendar.dom_collector",
        "learning_calendar.worker",
        "learning_calendar.sync",
    ):
        assert required in modules, required
    assert signature(marshal.loads(archive.extract("engine_main"))) == signature(
        compile((ROOT / "desktop/engine_main.py").read_bytes(), "engine_main", "exec")
    )
    with tempfile.TemporaryDirectory(prefix="calix-engine-check-") as folder:
        requests = [
            dict(id=1, method="bootstrap", params={}),
            dict(id=2, method="vault.state", params={}),
            dict(id=3, method="quit", params={}),
        ]
        completed = subprocess.run(
            [str(exe), "--data-dir", folder],
            input="".join(json.dumps(r) + "\n" for r in requests),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        assert completed.returncode == 0, completed.stderr
        responses = [json.loads(line) for line in completed.stdout.splitlines()]
        assert (
            next(r for r in responses if r.get("id") == 1)["result"]["version"]
            == "1.4.1"
        )
        assert (
            next(r for r in responses if r.get("id") == 2)["result"]["initialized"]
            is False
        )
    with tempfile.TemporaryDirectory(prefix="calix-open-pipe-check-") as folder:
        process = subprocess.Popen(
            [str(exe), "--data-dir", folder],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            process.stdin.write(b'{"id":77,"method":"quit","params":{}}\n')
            process.stdin.flush()
            assert json.loads(process.stdout.readline()) == dict(id=77, result=True)
            assert process.wait(timeout=15) == 0, process.stderr.read().decode(
                "utf-8", "replace"
            )
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdin.close()
            process.stdout.close()
            process.stderr.close()
    result = dict(
        source_matches_exe=True,
        embedded_modules=len(modules),
        stdio_round_trip=True,
        clean_exit=True,
    )
    print(json.dumps(result))
    return result


if __name__ == "__main__":
    check(sys.argv[1])
