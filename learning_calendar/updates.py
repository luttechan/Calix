"""Release metadata validation. Imported only when checking for updates."""

from dataclasses import dataclass
import re
from urllib.parse import urlsplit

RELEASES = "https://github.com/luttechan/Calix/releases"
LATEST_API = "https://api.github.com/repos/luttechan/Calix/releases/latest"
BETA_API = "https://api.github.com/repos/luttechan/Calix/releases?per_page=30"
MAX_INSTALLER = 220 * 1024 * 1024


def version_key(value):
    match = re.fullmatch(
        r"v?([0-9]+)\.([0-9]+)\.([0-9]+)(?:-r([0-9]+)|-beta\.([1-9][0-9]*))?",
        value if isinstance(value, str) else "",
    )
    if not match:
        raise ValueError("버전 정보를 확인할 수 없습니다.")
    major, minor, patch, revision, beta = (int(part or 0) for part in match.groups())
    # Historic hotfix labels used a concatenated patch number.
    if not beta:
        if (major, minor, patch) == (1, 5, 81):
            patch, revision = 8, 1
        elif (major, minor, patch) == (1, 4, 21):
            patch, revision = 2, 1
        elif (major, minor) == (1, 6) and patch in (11, 12, 13, 20, 30, 31, 32):
            patch, revision = divmod(patch, 10)
    return major, minor, patch, 0 if beta else 1, beta or revision


def trusted_download(url):
    try:
        parsed = urlsplit(url)
        return (
            parsed.scheme == "https"
            and parsed.hostname
            in ("github.com", "release-assets.githubusercontent.com")
            and parsed.port in (None, 443)
            and parsed.username is None
            and parsed.password is None
            and (
                parsed.hostname != "github.com"
                or parsed.path.startswith("/luttechan/Calix/releases/download/")
            )
        )
    except (TypeError, ValueError):
        return False


@dataclass(frozen=True)
class Release:
    tag: str
    url: str
    installer_url: str = ""
    digest: str = ""
    size: int = 0
    prerelease: bool = False
    published_at: str = ""


def parse_release(payload, *, allow_beta=False):
    if (
        not isinstance(payload, dict)
        or payload.get("draft")
    ):
        raise ValueError("릴리즈를 확인할 수 없습니다.")
    tag = payload.get("tag_name", "")
    prerelease = version_key(tag)[3] == 0
    if payload.get("prerelease", False) is not prerelease or (prerelease and not allow_beta):
        raise ValueError("릴리즈 채널을 확인할 수 없습니다.")
    published_at = payload.get("published_at")
    if not isinstance(published_at, str) or not re.fullmatch(r"[0-9]{4}(?:-[0-9]{2}){2}T[0-9]{2}(?::[0-9]{2}){2}Z", published_at):
        published_at = ""
    url = f"{RELEASES}/tag/{tag}"
    if payload.get("html_url") != url:
        raise ValueError("릴리즈 주소가 올바르지 않습니다.")
    assets = payload.get("assets", [])
    if not isinstance(assets, list):
        raise ValueError("설치 파일 정보가 올바르지 않습니다.")
    name = f'Calix-{tag.removeprefix("v")}-Setup-x64.exe'
    for asset in assets:
        if not isinstance(asset, dict) or asset.get("name") != name:
            continue
        download = asset.get("browser_download_url", "")
        digest = asset.get("digest", "")
        size = asset.get("size", 0)
        expected = f"{RELEASES}/download/{tag}/{name}"
        if (
            download != expected
            or not trusted_download(download)
            or not isinstance(digest, str)
            or not re.fullmatch(r"sha256:[a-fA-F0-9]{64}", digest)
        ):
            raise ValueError("설치 파일을 검증할 수 없습니다.")
        if type(size) is not int or not 0 < size <= MAX_INSTALLER:
            raise ValueError("설치 파일 크기가 올바르지 않습니다.")
        return Release(tag, url, download, digest[7:].lower(), size, prerelease, published_at)
    return Release(tag, url, prerelease=prerelease, published_at=published_at)


def select_release(payload, *, allow_beta=False):
    if not allow_beta:
        return parse_release(payload)
    if not isinstance(payload, list):
        raise ValueError("릴리즈 목록을 확인할 수 없습니다.")
    releases = []
    for item in payload:
        try:
            releases.append(parse_release(item, allow_beta=True))
        except ValueError:
            continue
    if not releases:
        raise ValueError("릴리즈를 확인할 수 없습니다.")
    stable = max((r for r in releases if not r.prerelease), key=lambda r: version_key(r.tag), default=None)
    beta = max((r for r in releases if r.prerelease), key=lambda r: version_key(r.tag), default=None)
    if not stable or not beta:
        return stable or beta
    stable_core = version_key(stable.tag)[:3]
    beta_core = version_key(beta.tag)[:3]
    # A beta published after an existing stable release can continue on its own channel.
    if beta_core > stable_core or (
        beta_core == stable_core and stable.published_at and beta.published_at > stable.published_at
    ):
        return beta
    return stable
