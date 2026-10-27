import pytest
from tools.check_runtime_security import check_openssl,check_release_python


@pytest.mark.parametrize('version',[(3,0,16),(3,5,8),(3,6,4),(4,0,2),(2,0,0)])
def test_reject_old_or_unaudited_tls_branch(version):
    assert not check_openssl(version)


@pytest.mark.parametrize('version',[(3,5,9),(3,6,5),(4,0,3)])
def test_accept_audited_security_patch(version):
    assert check_openssl(version)


def test_release_python_cannot_silently_fall_back_to_312():
    assert check_release_python((3,14,10))
    assert not check_release_python((3,12,10))
    assert not check_release_python((3,14,7))
