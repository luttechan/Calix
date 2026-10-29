"""Isolated fresh install, replacement, binary equality and uninstall check."""
from pathlib import Path
import hashlib,json,subprocess,sys,time

def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def check(setup,bundle,target):
    setup,bundle,target=map(lambda p:Path(p).resolve(),(setup,bundle,target))
    assert not target.exists(),'Use a new isolated test directory.'
    args=[str(setup),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/NOICONS',f'/DIR={target}']
    for attempt in range(2):
        subprocess.run(args,check=True,timeout=120)
        for source in bundle.rglob('*'):
            if source.is_file():assert digest(source)==digest(target/source.relative_to(bundle)),source
        # Files outside the installer file list survive an upgrade and uninstall.
        marker=target/'personal-test.txt'
        if attempt:assert marker.read_text(encoding='utf-8')=='preserve'
        else:marker.write_text('preserve',encoding='utf-8')
    subprocess.run([str(target/'unins000.exe'),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART'],check=True,timeout=60)
    deadline=time.monotonic()+15
    while (target/'Calix.exe').exists() and time.monotonic()<deadline:time.sleep(.1)
    assert not (target/'Calix.exe').exists() and marker.read_text(encoding='utf-8')=='preserve'
    print(json.dumps(dict(fresh_install=True,upgrade=True,binary_equality=True,uninstall=True,unowned_data_preserved=True)))

if __name__=='__main__':check(*sys.argv[1:])
