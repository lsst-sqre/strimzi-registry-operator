"""Tests for the certprocessor module.
"""

import pytest

from strimziregistryoperator.certprocessor import create_truststore


@pytest.fixture
def cluster_ca_cert():
    return (
        '-----BEGIN CERTIFICATE-----\n'
        'MIIDLTCCAhWgAwIBAgIJAI8I0CsaV4EoMA0GCSqGSIb3DQEBCwUAMC0xEzARBgNV\n'
        'BAoMCmlvLnN0cmltemkxFjAUBgNVBAMMDWNsdXN0ZXItY2EgdjAwHhcNMTkxMDE1\n'
        'MjEyNTMyWhcNMjAxMDE0MjEyNTMyWjAtMRMwEQYDVQQKDAppby5zdHJpbXppMRYw\n'
        'FAYDVQQDDA1jbHVzdGVyLWNhIHYwMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIB\n'
        'CgKCAQEA8ul21rUrCxsqqBhC9u3lWMY6uDeBMfmxzNNnWd8mUqHKBaN3IGV045w4\n'
        'F1SjaUzCzDJUT34eYjRVsIZzc8AjM+sdKywRRYNRe12LS6VAhroqRoO9tH399Nd9\n'
        'JoEUhSIF4clao3gm7YV2DCNSvTR5Jz7QPWIF1EaSr/CRaPezoQxEX51Ndylf7fix\n'
        '1ay3AJHJ38NyyRXo65tHdJQFnoUGHL8GACVg+6GngH4sD5cPN/P/PaEHL7MpIcjI\n'
        'sYF7D69rBY+SV0eb0sYrWojkPVb3o+ICZ0A+fnnxXAnFjkV7SxqqzcQO7HH8w3yV\n'
        'zx8hPuBtS1bB46jyOtFJ9Q5Q8GtV4QIDAQABo1AwTjAdBgNVHQ4EFgQUug/aKVnl\n'
        'Kll2ICMB9FICtICMKTUwHwYDVR0jBBgwFoAUug/aKVnlKll2ICMB9FICtICMKTUw\n'
        'DAYDVR0TBAUwAwEB/zANBgkqhkiG9w0BAQsFAAOCAQEAwnXcVfMD4H+dOlBURxcU\n'
        'R4BX9ufRXub51ew2iqi/0iACKQ98uTib02jS2TEJREDkCcugV7C+VUFFn1PtIgIn\n'
        'd5RLlq2hdvsC2Q8BH47lo3M3tg3zC4iHpf32eKiyZ0vb96oCf5ENBgeGr33u7VoT\n'
        '+BQw4Ir0rL5pl/3hrJuUWRTZckSOs6C28G9Z3lLKnxIsQ4Q5yER3OuYneyrOrtaZ\n'
        '1JvPaImsjPtSp1zL/fr+qixLW7irdqd+MK3+GN4fDf9lWkvLT3sLzoSxvaSi4pNd\n'
        '9CFShrF5rvQCSlPUvr+l74IwimEmNXm7xr6fuU+9w9DzU7HpQ+TbOwNsEZb5pSpt\n'
        'fQ==\n'
        '-----END CERTIFICATE-----\n'
    )


def test_create_truststore(cluster_ca_cert):
    truststore = create_truststore(cluster_ca_cert, 'test1234')
    assert isinstance(truststore, bytes)
    assert len(truststore) > 0
