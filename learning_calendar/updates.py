"""Release metadata validation. Imported only when checking for updates."""
from dataclasses import dataclass
import re
from urllib.parse import urlsplit

RELEASES='https://github.com/luttechan/Calix/releases'
LATEST_API='https://api.github.com/repos/luttechan/Calix/releases/latest'
MAX_INSTALLER=220*1024*1024


def version_key(value):
    match=re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)(?:-r(\d+))?',value)
    if not match:raise ValueError('버전 정보를 확인할 수 없습니다.')
    return tuple(int(part or 0) for part in match.groups())


def trusted_download(url):
    try:
        parsed=urlsplit(url)
        return (parsed.scheme=='https' and parsed.hostname in ('github.com','release-assets.githubusercontent.com')
                and parsed.port in (None,443) and parsed.username is None and parsed.password is None
                and (parsed.hostname!='github.com' or parsed.path.startswith('/luttechan/Calix/releases/download/')))
    except (TypeError,ValueError):return False


@dataclass(frozen=True)
class Release:
    tag: str
    url: str
    installer_url: str=''
    digest: str=''
    size: int=0


def parse_release(payload):
    if not isinstance(payload,dict) or payload.get('draft') or payload.get('prerelease'):
        raise ValueError('정식 릴리즈를 확인할 수 없습니다.')
    tag=payload.get('tag_name','');version_key(tag)
    url=f'{RELEASES}/tag/{tag}'
    if payload.get('html_url')!=url:raise ValueError('릴리즈 주소가 올바르지 않습니다.')
    assets=payload.get('assets',[])
    if not isinstance(assets,list):raise ValueError('설치 파일 정보가 올바르지 않습니다.')
    name=f'Calix-{tag.removeprefix("v")}-Setup-x64.exe'
    for asset in assets:
        if not isinstance(asset,dict) or asset.get('name')!=name:continue
        download=asset.get('browser_download_url','');digest=asset.get('digest','');size=asset.get('size',0)
        expected=f'{RELEASES}/download/{tag}/{name}'
        if download!=expected or not trusted_download(download) or not isinstance(digest,str) or not re.fullmatch(r'sha256:[a-fA-F0-9]{64}',digest):
            raise ValueError('설치 파일을 검증할 수 없습니다.')
        if type(size) is not int or not 0<size<=MAX_INSTALLER:raise ValueError('설치 파일 크기가 올바르지 않습니다.')
        return Release(tag,url,download,digest[7:].lower(),size)
    return Release(tag,url)
