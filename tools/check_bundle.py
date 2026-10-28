"""Verify embedded app code and runtime-only distribution contents."""
from pathlib import Path
import sys,json,types,marshal
from PyInstaller.archive.readers import CArchiveReader
from bundle_policy import RUNTIME_ASSETS,keep_entry

ROOT=Path(__file__).resolve().parents[1]


def signature(value):
    if isinstance(value,types.CodeType):
        return value.co_code,value.co_names,value.co_varnames,tuple(signature(item) for item in value.co_consts)
    return value


def check(folder):
    folder=Path(folder);exe=folder/'Calix.exe';archive=CArchiveReader(str(exe))
    pyz=archive.open_embedded_archive(next(name for name in archive.toc if name.lower().endswith('.pyz')))
    modules=[]
    for source in (ROOT/'learning_calendar').glob('*.py'):
        name='learning_calendar' if source.stem=='__init__' else 'learning_calendar.'+source.stem
        assert name in pyz.toc,name
        assert signature(pyz.extract(name))==signature(compile(source.read_bytes(),str(source),'exec')),name
        modules.append(name)
    assert signature(marshal.loads(archive.extract('main')))==signature(compile((ROOT/'main.py').read_bytes(),str(ROOT/'main.py'),'exec'))
    files=[path for path in folder.rglob('*') if path.is_file()]
    for path in files:
        relative=path.relative_to(folder).as_posix()
        assert path.suffix.lower() not in {'.py','.pyc','.har','.db','.dpapi'},relative
        assert keep_entry(relative),relative
        assert not path.name.startswith(('Qt63D','Qt6Quick3D')),relative
    for path in RUNTIME_ASSETS:assert (folder/'_internal'/path).is_file(),path
    assert not (folder/'_internal/asset/style/PretendardVariable.ttf').exists()
    assert not (folder/'_internal/asset/profile.png').exists()
    size=sum(path.stat().st_size for path in files)
    assert size<450*1024**2,'Unexpected runtime size'
    return dict(embedded_modules=len(modules),source_matches_exe=True,standalone_source_files=0,files=len(files),unpacked_bytes=size,unpacked_mb=round(size/1024**2,2))


if __name__=='__main__':
    result=check(sys.argv[1]);print(json.dumps(result))
    if len(sys.argv)>2:Path(sys.argv[2]).write_text(json.dumps(result,indent=2),encoding='utf-8')
