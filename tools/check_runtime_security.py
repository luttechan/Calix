"""Fail the release build if it falls back to an outdated TLS runtime."""
import json
import re
import ssl
import sys

MINIMUM_PATCH={(3,5):9,(3,6):5,(4,0):3}


def parse_openssl_version(value):
    match=re.match(r'^OpenSSL (\d+)\.(\d+)\.(\d+)(?:\s|$)',value)
    return tuple(map(int,match.groups())) if match else ()


def check_openssl(version):
    minimum=MINIMUM_PATCH.get(tuple(version[:2]))
    return minimum is not None and len(version)>=3 and version[2]>=minimum


def check_release_python(version):
    return tuple(version[:3])==(3,14,10)


def main():
    result=dict(python=sys.version.split()[0],openssl=ssl.OPENSSL_VERSION,
                tls_patch_current=check_openssl(parse_openssl_version(ssl.OPENSSL_VERSION)),
                release_python=check_release_python(sys.version_info))
    print(json.dumps(result))
    return 0 if result['tls_patch_current'] and result['release_python'] else 1


if __name__=='__main__':raise SystemExit(main())
