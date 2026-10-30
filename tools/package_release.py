"""Create a runtime-only ZIP. Sources remain in the repository."""
from pathlib import Path
import sys,zipfile,hashlib,json

ROOT=Path(__file__).resolve().parents[1]
LAUNCHER='''@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
start "" /D "%~dp0" "%~dp0Calix.exe"
'''.replace('\n','\r\n')
README='Calix 1.2.0-r1\n\nWindows 10 / 11, 64비트. Calix.exe 실행.\n\n사용 설명서: https://luttechan.github.io/calix/guide/\n'
NOTICES='''Calix uses Python, Qt/PySide6, Requests, cryptography, keyring and tzdata.
Bundled dependency notices: _internal/licenses/
Font license: _internal/asset/style/Pretendard-OFL.txt
Holiday data license: _internal/asset/calendar/HOLIDAYS-MIT.txt
Sources: https://github.com/luttechan/Calix
Qt: https://code.qt.io/ and https://www.qt.io/licensing/
'''


def font_notice():
    license_text=(ROOT/'asset/style/Pretendard-OFL.txt').read_text(encoding='utf-8')
    copyright=license_text.partition('This Font Software')[0].strip()
    return 'Font: Calix Sans (derived from Pretendard)\n'+copyright+'\nSIL Open Font License 1.1.\n'


def package(bundle,output):
    bundle=Path(bundle).resolve();output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    assert (bundle/'Calix.exe').is_file() and not (bundle/'source').exists()
    archive_path=output/'Calix-1.2.0-r1-Windows-x64.zip';count=0
    with zipfile.ZipFile(archive_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for path in sorted(bundle.rglob('*')):
            if not path.is_file():continue
            relative=path.relative_to(bundle)
            assert path.resolve().is_relative_to(bundle) and not path.is_symlink()
            assert relative.parts[0] in {'Calix.exe','_internal'},relative
            archive.write(path,'Calix 1.2.0-r1/'+relative.as_posix());count+=1
        for name,content in [('run_windows.bat',LAUNCHER),('README.md',README),('THIRD_PARTY_NOTICES.txt',NOTICES+'\n'+font_notice()),('LICENSE',(ROOT/'LICENSE').read_text(encoding='utf-8'))]:
            archive.writestr('Calix 1.2.0-r1/'+name,content.encode('utf-8'))
    with archive_path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    (output/'SHA256SUMS.txt').write_text(f'{digest}  {archive_path.name}\n',encoding='utf-8')
    (output/'THIRD_PARTY_NOTICES.txt').write_text(NOTICES+'\n'+font_notice(),encoding='utf-8')
    return dict(files=count+4,zip_bytes=archive_path.stat().st_size,sha256=digest)


if __name__=='__main__':print(json.dumps(package(sys.argv[1],sys.argv[2])))
