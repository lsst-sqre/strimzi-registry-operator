"""Tests for the certprocessor module.
"""

import pytest

from strimziregistryoperator.certprocessor import (
    create_truststore, create_keystore)


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


@pytest.fixture
def user_ca_cert():
    return (
        '-----BEGIN CERTIFICATE-----\n'
        'MIIDLTCCAhWgAwIBAgIJAICpKjuRE/WNMA0GCSqGSIb3DQEBCwUAMC0xEzARBgNV\n'
        'BAoMCmlvLnN0cmltemkxFjAUBgNVBAMMDWNsaWVudHMtY2EgdjAwHhcNMTkxMDE1\n'
        'MjEyNTMyWhcNMjAxMDE0MjEyNTMyWjAtMRMwEQYDVQQKDAppby5zdHJpbXppMRYw\n'
        'FAYDVQQDDA1jbGllbnRzLWNhIHYwMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIB\n'
        'CgKCAQEAzgApIGlLC3BclTlGqjWogNeLH1n9xodAYZu9WSODAxmR4EuN5UEvGHvv\n'
        'F9azHWyWawFS1SKTK0XX4JwLTU4VKfr2XqZC7GldCaY1Uc0ZxezUzJItVPd1Uaf0\n'
        '+54wZNTAyYmYZYJGC6jyEmy7QUu3hc3mW7D03rlHyaIM1o2d4b3l0Tpfh3gWU7hR\n'
        'Zy79g5yv6OV23IHJ7SOILdzzDf7YsGpCjmWabt14892+buRLR1JaZ2lDjHWsRGUz\n'
        '4X1ZttgTOnZH0bhKUwj4J3DNrge5CIIbG41jAOQbgIfXMgryxgXAXAxQWwaXDOU/\n'
        'yVTuqvhNjM5MNflcOfpgBclaZmmSaQIDAQABo1AwTjAdBgNVHQ4EFgQUwQtsJEef\n'
        'QKJvZLzCVRjKK3fV/xowHwYDVR0jBBgwFoAUwQtsJEefQKJvZLzCVRjKK3fV/xow\n'
        'DAYDVR0TBAUwAwEB/zANBgkqhkiG9w0BAQsFAAOCAQEAd4JSZJYDx9ckPPRE+her\n'
        '303Bju1AtT8QB+0xyL3NGOY+xvwCtDZKUP9TjyWwhz9rOJAZRq8daaOg/OVMpDHm\n'
        'AwGjitm/U+4r7NZ12U+kbmyb0MFTr4khd0wZKHIZ9C35v8ECwpRnFgMhHSYgzXd7\n'
        'IKwzpRkwsMe0bm4LSJkwdYoQt7Jqhb6XE6ckDA2UWlbB7c6VPYTZe1XxiulgCGTb\n'
        'GPPIWBIFOVElwI2BL74ql/3C54HcXR2Y5Rcz9bvmfkwqlNUdKM1rrzxYxCktTt1y\n'
        '291ZLx6zFy1Gv6ArOhHGcxzb7WaXKcz479srN2hpHVh8LJsbdFBgt5yIOhEX+6zG\n'
        'Yw==\n'
        '-----END CERTIFICATE-----\n'
    )


@pytest.fixture
def user_cert():
    return (
        '-----BEGIN CERTIFICATE-----\n'
        'MIICuDCCAaACCQDebhOM2cAAcDANBgkqhkiG9w0BAQsFADAtMRMwEQYDVQQKDApp\n'
        'by5zdHJpbXppMRYwFAYDVQQDDA1jbGllbnRzLWNhIHYwMB4XDTE5MTAxNzE3NTIx\n'
        'MFoXDTIwMTAxNjE3NTIxMFowDzENMAsGA1UEAwwEZGVtbzCCASIwDQYJKoZIhvcN\n'
        'AQEBBQADggEPADCCAQoCggEBANKdbGH9UJXWaz0LnK96wPmrjQLSRx6CVRh3IyCJ\n'
        'JWVwsRoaOjQI/k7UrCIiZPzUF8Kr+p5fRr0/TBR8MdvK2qLKjWj+H9VXVhDZUNaJ\n'
        'HmtmUuo30A/KBYeh0yXgLv63TC/3t1zPn7zuaB3ZzVYDKUsa/c3mSO0NelYuR9Yq\n'
        '/3YHNTOncjM8p+Keh5buPVYQY1X6r/G6btoKKQ9FDZtiJdwWI7uffzuF+guh881I\n'
        'UT7HcF2YKzTXgp9v3/dKFzUBmhn/zNGThyphkkNMT2ysqLergYK3wVo5ZvdqmN9u\n'
        'ScE93zo6/BBLQphktMhuWacYW0hBst8Kmy0RqNcbvCGDxJkCAwEAATANBgkqhkiG\n'
        '9w0BAQsFAAOCAQEAUEVSH3tZT1jb1kobK1OBcGUEwH09IEV+uAU54I+/xmR9X3VF\n'
        'RuRLCRB9ECxuPk+BQGEDyyrM3omejfkx293nWmnOt0RviVDfbGi4BiTRcl1VbmNQ\n'
        'iRYZTspRKu6M3J0vKWwOxZKO611YNKT5rJLEW0KPNtshTxSgzMKbvtu4WAs9jLIM\n'
        'U81kYytd+JQ8Lj32zEBJO7K291EYv0pHUUmY2x05OJTtWe2hbthqZWbv5dx9f6/9\n'
        '104rcQuOtx2ZqEjsiqV8CQiXyF/Bgaq8/B/JjQzwBmtc4N84xvl7BDcuNaz/1Dqx\n'
        'yLna+iqtWx9f4TS4wdv7QP2VjIBEI7T/1TcU3w==\n'
        '-----END CERTIFICATE-----\n'
    )


@pytest.fixture
def user_key():
    return (
        '-----BEGIN PRIVATE KEY-----\n'
        'MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDSnWxh/VCV1ms9\n'
        'C5yvesD5q40C0kceglUYdyMgiSVlcLEaGjo0CP5O1KwiImT81BfCq/qeX0a9P0wU\n'
        'fDHbytqiyo1o/h/VV1YQ2VDWiR5rZlLqN9APygWHodMl4C7+t0wv97dcz5+87mgd\n'
        '2c1WAylLGv3N5kjtDXpWLkfWKv92BzUzp3IzPKfinoeW7j1WEGNV+q/xum7aCikP\n'
        'RQ2bYiXcFiO7n387hfoLofPNSFE+x3BdmCs014Kfb9/3Shc1AZoZ/8zRk4cqYZJD\n'
        'TE9srKi3q4GCt8FaOWb3apjfbknBPd86OvwQS0KYZLTIblmnGFtIQbLfCpstEajX\n'
        'G7whg8SZAgMBAAECggEBAJFs6Z1vj+kmOL3Z+sKf/AdpEODV2Q2T6LYP7U1V5WB5\n'
        'w4/GdFHhs9cyufiHzztUJ2Pf5BjeqLWbsyih6LtfAkBNo/7PGaPxvhe8NjksTLjT\n'
        '2oSnLR7523+fmXAZr9lpL04fuZh4NE/8Ph/+d+3gGO8nIAC/9bLZD5PaOPgEkIgp\n'
        'iEJJwO42iiUsrl39h7MelG0h2zV2jH3XKrUTOFK4xgQQm4LCDR/SkkvzMTkt12qT\n'
        '5og6qQqyvpgbGlJT+fcCF7YmK0RU8Al0rDiOOTOHzMcrQX9n72qvxfZr6clRGCwP\n'
        'YvB0ZZOJgIqxC01eGUa8IIM6Y7Y3WV76cK7syW8/v9ECgYEA+1shTI/of8Vox0n3\n'
        'g2LF8yj8ePzqrGxb2GhV1AEJo449LIrBxK9xKTlN1J+yOdjz+nj3oujQQrtdLM/G\n'
        'k9Xkkl9KqgQjYvVIXzS0gMgU1tke76t8Z7n4RyxFvNJm2r7dXfwuRnu54Hab6E3j\n'
        'V/zq+NH+uSNM4UVnwWrADzhHjl8CgYEA1oGYY+mpgri40enT0rmqNLs/Yj/FXJ5+\n'
        'RVvi6DIt06wx5jkMhpp5l7ExCluBZ8AYpzkjl2fFwSF0md6uXtq2NkaFPs2HBGCz\n'
        'Pz87LWzaQZ3JAe3Oq6QD7qGcBZcpaelIukSX166v0ZPwGAAFxo2zyBGuwz1dSNDD\n'
        'rh6NRpsdIAcCgYALqsU26o8eLymX5oUIojMSAFsHuqWh7z2sI9uoBYxO/TE1uhMY\n'
        'cBROl4xXTDpXmQxqGedUtn3EOzIt/E75WbpMWQP8NEj4NO5xDN88Aw2Ek3tuIIWb\n'
        'wvQVSabLBvEjQizASg5T0zZjht3hwIvG78RwXD74lPzij/gq8CuOCUy4/QKBgQCB\n'
        'aqb6gNtYlwJLA3xdQs9CCUbwi/ETNDyStCFuXffwIY/pirnX7BM4RhuEWDj205sM\n'
        'KRkkG+Pf5cNnokYpzGLq1BlIDtBK/9ylaAzYFziHJh9EHqn2PHpy2uY7KTw/PhQ2\n'
        '7XN/GVHSbCMLF9hkNtIk/yYlfTxu1iV5Q82Qr70euQKBgGs5Cw4pXNivzthHp3uF\n'
        'Kp+9Ce6yIOVF2wP5dqDcZOt/gxxu3BkIXqQ8O4tGB7/zH+5xChsUZNj0FlawPxmc\n'
        'eGMEtoxHHeaST6lhHHT2hoIN4+eK6ZypCmWz2gE1Mkt5QfgQSVACD4hUpD1zhcps\n'
        'ILMF7rg7broq4A38DY4mhV3t\n'
        '-----END PRIVATE KEY-----\n'
    )


def test_create_truststore(cluster_ca_cert):
    truststore = create_truststore(cluster_ca_cert, 'test1234')
    assert isinstance(truststore, bytes)
    assert len(truststore) > 0


def test_create_keystore(user_ca_cert, user_cert, user_key):
    keystore = create_keystore(user_ca_cert, user_cert, user_key, 'test1234')
    assert isinstance(keystore, bytes)
    assert len(keystore) > 0
