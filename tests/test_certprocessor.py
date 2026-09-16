"""Tests for the certprocessor module."""

import subprocess
from typing import NamedTuple

import pytest

from strimziregistryoperator.certprocessor import (
    create_keystore,
    create_truststore,
)


class CertificateMaterial(NamedTuple):
    cluster_ca_cert: str
    user_ca_cert: str
    user_cert: str
    user_key: str


def _run_openssl(*args: str) -> None:
    subprocess.run(
        ["openssl", *args],
        capture_output=True,
        check=True,
    )


@pytest.fixture(scope="module")
def certificate_material(
    tmp_path_factory: pytest.TempPathFactory,
) -> CertificateMaterial:
    cert_dir = tmp_path_factory.mktemp("certificates")

    cluster_ca_key_path = cert_dir / "cluster-ca.key"
    cluster_ca_cert_path = cert_dir / "cluster-ca.crt"
    _run_openssl(
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-keyout",
        str(cluster_ca_key_path),
        "-out",
        str(cluster_ca_cert_path),
        "-days",
        "1",
        "-nodes",
        "-subj",
        "/CN=Test Cluster CA",
    )

    user_ca_key_path = cert_dir / "user-ca.key"
    user_ca_cert_path = cert_dir / "user-ca.crt"
    _run_openssl(
        "req",
        "-x509",
        "-newkey",
        "rsa:2048",
        "-keyout",
        str(user_ca_key_path),
        "-out",
        str(user_ca_cert_path),
        "-days",
        "1",
        "-nodes",
        "-subj",
        "/CN=Test User CA",
    )

    user_key_path = cert_dir / "user.key"
    user_csr_path = cert_dir / "user.csr"
    user_cert_path = cert_dir / "user.crt"
    _run_openssl(
        "req",
        "-newkey",
        "rsa:2048",
        "-keyout",
        str(user_key_path),
        "-out",
        str(user_csr_path),
        "-nodes",
        "-subj",
        "/CN=Test User",
    )
    _run_openssl(
        "x509",
        "-req",
        "-in",
        str(user_csr_path),
        "-CA",
        str(user_ca_cert_path),
        "-CAkey",
        str(user_ca_key_path),
        "-CAcreateserial",
        "-out",
        str(user_cert_path),
        "-days",
        "1",
        "-sha256",
    )

    return CertificateMaterial(
        cluster_ca_cert=cluster_ca_cert_path.read_text(),
        user_ca_cert=user_ca_cert_path.read_text(),
        user_cert=user_cert_path.read_text(),
        user_key=user_key_path.read_text(),
    )


@pytest.fixture(scope="module")
def cluster_ca_cert(certificate_material: CertificateMaterial) -> str:
    return certificate_material.cluster_ca_cert


@pytest.fixture(scope="module")
def user_ca_cert(certificate_material: CertificateMaterial) -> str:
    return certificate_material.user_ca_cert


@pytest.fixture(scope="module")
def user_cert(certificate_material: CertificateMaterial) -> str:
    return certificate_material.user_cert


@pytest.fixture(scope="module")
def user_key(certificate_material: CertificateMaterial) -> str:
    return certificate_material.user_key


def test_create_truststore(cluster_ca_cert: str) -> None:
    truststore, password = create_truststore(
        cluster_ca_cert, password="test1234"
    )
    assert isinstance(truststore, bytes)
    assert len(truststore) > 0
    assert password == "test1234"


def test_create_keystore(
    user_ca_cert: str, user_cert: str, user_key: str
) -> None:
    keystore, password = create_keystore(
        user_ca_cert, user_cert, user_key, password="test1234"
    )
    assert isinstance(keystore, bytes)
    assert len(keystore) > 0
    assert password == "test1234"
