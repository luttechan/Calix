import pytest
from tools.bundle_policy import keep_tls_library


@pytest.mark.parametrize('required,unused',[
    ({'libcrypto-3.dll','libssl-3.dll'},{'libcrypto-3-x64.dll','libssl-3-x64.dll'}),
    ({'libcrypto-3-x64.dll','libssl-3-x64.dll'},{'libcrypto-3.dll','libssl-3.dll'}),
])
def test_tls_files_follow_interpreter_imports_instead_of_filename_assumptions(required,unused):
    assert all(keep_tls_library('_internal/'+name,required) for name in required)
    assert not any(keep_tls_library('_internal/'+name,required) for name in unused)
    assert keep_tls_library('Qt6Network.dll',required)
