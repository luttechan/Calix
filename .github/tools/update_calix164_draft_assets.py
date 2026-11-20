from hashlib import file_digest
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


repo = os.environ['GH_REPO']
source = os.environ['SOURCE']
endpoint = f'repos/{repo}/releases/452901539'
previous = 'ee7c867277dcf425a4cc2f39f0529e630169e73b'
notes = ('- Dev Lab 테마 팔레트 편집\n'
         '- 오류음과 동기화 완료음 Notification 1–10\n'
         '- 달력 연도, 월 이동 및 드롭다운 디자인 통일\n'
         '- 체크리스트 열 너비와 기한 편집\n'
         '- 실행 잠금 화면, 매 실행 업데이트 확인\n'
         '- 시간표 강의 상세의 긴 제목 줄바꿈\n'
         '- 시간표 요일 정렬 및 수업 상세 정리\n'
         '- Windows 작업표시줄 버전 명칭 표시\n'
         '- 안내 문구 정리')
files = ('Calix-1.6.4-Setup-x64.exe', 'Calix-1.6.4-Windows-x64.zip', 'SHA256SUMS.txt')


def gh(*args):
    return subprocess.check_output(['gh', *args], text=True, encoding='utf-8')


def release():
    value = json.loads(gh('api', endpoint))
    assert value['draft'] and (value['tag_name'] == 'v1.6.4' or value['tag_name'].startswith('untagged-'))
    return value


def assets():
    return {asset['name']: asset for asset in release()['assets']}


def rename(asset, name):
    gh('api', '-X', 'PATCH', f'repos/{repo}/releases/assets/{asset["id"]}', '-f', f'name={name}')


latest = gh('api', f'repos/{repo}/releases/latest', '--jq', '.tag_name').strip()
assert release()['target_commitish'] in (previous, source)
hashes = {}
for name in files:
    with (Path('packages') / name).open('rb') as stream:
        hashes[name] = 'sha256:' + file_digest(stream, 'sha256').hexdigest()

with tempfile.TemporaryDirectory() as folder:
    uploads = []
    current = assets()
    for name, digest in hashes.items():
        if current.get(name, {}).get('digest') == digest:
            continue
        pending = name + '.pending'
        if pending in current:
            assert current[pending]['digest'] == digest, pending
        else:
            destination = Path(folder) / pending
            shutil.copy2(Path('packages') / name, destination)
            uploads.append(str(destination))
    if uploads:
        gh('release', 'upload', release()['tag_name'], *uploads)

current = assets()
for name, digest in hashes.items():
    if current.get(name, {}).get('digest') != digest:
        assert current[name + '.pending']['digest'] == digest, name
for name, digest in hashes.items():
    if current.get(name, {}).get('digest') == digest:
        continue
    prior = name + '.previous'
    if name in current:
        assert prior not in current
        rename(current[name], prior)
    rename(current[name + '.pending'], name)
gh('api', '-X', 'PATCH', endpoint, '-F', 'draft=true', '-f', 'tag_name=v1.6.4', '-f', f'target_commitish={source}', '-f', f'body={notes}')
updated = release()
assert updated['target_commitish'] == source and updated['tag_name'] == 'v1.6.4'
current = {asset['name']: asset for asset in updated['assets']}
assert all(current[name]['digest'] == digest for name, digest in hashes.items())
for name in files:
    prior = current.get(name + '.previous')
    if prior:
        gh('api', '-X', 'DELETE', f'repos/{repo}/releases/assets/{prior["id"]}')
assert set(assets()) == set(hashes)
assert gh('api', f'repos/{repo}/releases/latest', '--jq', '.tag_name').strip() == latest
print(updated['html_url'])
