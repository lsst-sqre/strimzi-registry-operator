"""Utilities for generating the truststore and keystore for the Schema Registry
based on the cluster's CA cert and the KafkaUser's key.
"""

__all__ = ("create_keystore", "create_secret", "create_truststore")

import base64
import secrets
import string
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

import kopf
import structlog
from kubernetes.client.exceptions import ApiException

from strimziregistryoperator.k8s import get_secret


def create_secret(
    *,
    kafka_username: str,
    namespace: str,
    cluster: str,
    owner: kopf.Body | None,
    k8s_client: Any,
    cluster_ca_secret: dict[str, Any] | None = None,
    client_secret: dict[str, Any] | None = None,
    logger: Any | None = None,
) -> dict[str, Any]:
    """Create and deploy a new Secret for the StrimziSchemaRegistry with
    JKS-formatted key and truststores.

    Parameters
    ----------
    kafka_username : `str`
        Name of the associated KafkaUser.
    namespace : `str`
        The name of the Kubernetes namespace where the Strimzi Kafka cluster
        operates.
    cluster : `str`
        The name of the Strimzi Kafka cluster.
    owner :
        The object that owns the Secret; usually the StrimziSchemaRegistry.
    k8s_client
        A Kubernetes client (see
        `strimziregistryoperator.k8s.create_k8sclient`).
    cluster_ca_secret : `dict`, optional
        The Kubernetes Secret resource body for the cluster CA secret,
        named ``<cluster>-cluster-ca-cert``. If not set, the resource will be
        automatically retrieved for you.
    client_secret : `dict`, optional
        The Kubernetes secret resource created by Strimzi with the certificates
        for the KafkaUser. This secret is named after ``kafka_username``. If
        not set, this resource will be retrieved automatically for you.
    logger : `logging.Logger`, optional
        Logger to use for logging messages. If not provided, a default logger
        will be used.
    """
    if logger is None:
        logger = structlog.getLogger(__name__)

    key_prefix = "strimziregistryoperator.roundtable.lsst.codes"
    ca_version_key = f"{key_prefix}/caSecretVersion"
    user_version_key = f"{key_prefix}/clientSecretVersion"

    if cluster_ca_secret is None:
        cluster_ca_secret = get_secret(
            namespace=namespace,
            name=f"{cluster}-cluster-ca-cert",
            k8s_client=k8s_client,
        )
        logger.info("Retrieved cluster CA certificate")

    cluster_secret_version = cluster_ca_secret["metadata"]["resourceVersion"]
    logger.info(f"Cluster CA certificate version: {cluster_secret_version}")
    cluster_ca_cert = decode_secret_field(cluster_ca_secret["data"]["ca.crt"])

    if client_secret is None:
        client_secret = get_secret(
            namespace=namespace, name=kafka_username, k8s_client=k8s_client
        )
        logger.info("Retrieved KafkaUser client secret.")

    client_secret_version = client_secret["metadata"]["resourceVersion"]
    logger.info(f"Client secret version: {client_secret_version}")
    client_ca_cert = decode_secret_field(client_secret["data"]["ca.crt"])
    client_cert = decode_secret_field(client_secret["data"]["user.crt"])
    client_key = decode_secret_field(client_secret["data"]["user.key"])

    jks_secret_name = f"{kafka_username}-jks"

    try:
        jks_secret = get_secret(
            namespace=namespace, name=jks_secret_name, k8s_client=k8s_client
        )
        annotations = jks_secret["metadata"]["annotations"]
        if (
            annotations.get(ca_version_key) == cluster_secret_version
            and annotations.get(user_version_key) == client_secret_version
        ):
            logger.info("JKS secret is up-to-date.")
            return jks_secret
        logger.info("JKS secret is outdated. Deleting...")
        delete_secret(
            namespace=namespace, name=jks_secret_name, k8s_client=k8s_client
        )
    except ApiException as e:
        if e.status == 404:
            logger.info("JKS secret does not exist. Will create.")
        else:
            logger.exception("Error retrieving JKS secret.")
            raise
    except Exception:
        logger.exception("Failed to retrieve or delete existing JKS secret.")
        raise

    # Create new keystore and truststore
    truststore, truststore_password = create_truststore(cluster_ca_cert)
    keystore, keystore_password = create_keystore(
        client_ca_cert, client_cert, client_key
    )

    secret_data = {
        "truststore.jks": b64(truststore),
        "keystore.jks": b64(keystore),
        "truststore_password": b64(truststore_password),
        "keystore_password": b64(keystore_password),
    }

    metadata = k8s_client.V1ObjectMeta(
        name=jks_secret_name,
        annotations={
            ca_version_key: cluster_secret_version,
            user_version_key: client_secret_version,
        },
    )

    secret = k8s_client.V1Secret(
        metadata=metadata, type="Opaque", data=secret_data
    )

    secret_body = k8s_client.CoreV1Api().api_client.sanitize_for_serialization(
        secret
    )

    kopf.adopt(secret_body, owner=owner)
    k8s_client.CoreV1Api().create_namespaced_secret(
        namespace=namespace, body=secret_body
    )

    logger.info("Created new JKS secret")
    return secret_body


def decode_secret_field(value: str) -> str:
    return base64.b64decode(value).decode("utf-8")


def b64(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return base64.b64encode(data).decode("utf-8")


def delete_secret(
    *,
    namespace: str,
    name: str,
    k8s_client: Any,
) -> None:
    """Delete a Kubernetes Secret.

    Parameters
    ----------
    namespace : `str`
        The namespace where the Secret is located.
    name : `str`
        The name of the Secret to delete.
    k8s_client : `Any`
        A Kubernetes client (see
        `strimziregistryoperator.k8s.create_k8sclient`).
    """
    v1_api = k8s_client.CoreV1Api()
    v1_api.delete_namespaced_secret(name=name, namespace=namespace)


@lru_cache(maxsize=128)
def create_truststore(
    cert: str,
    password: str | None = None,
) -> tuple[bytes, str]:
    """Create a JKS-formatted truststore using the cluster's CA certificate.

    Parameters
    ----------
    cert : `str`
        The content of the Kafka cluster CA certificate. You can get this from
        a Kubernetes Secret named ``<cluster>-cluster-ca-cert``, and
        specifially the secret key named ``ca.crt``. See
        `get_cluster_ca_cert`.
    password : `str`, optional
        Password to protect the output truststore with. If not set, a random
        password will be generated.

    Returns
    -------
    truststore_content : `bytes`
        The content of a JKS truststore containing the cluster CA certificate.
    password : `str`
        The password generated for the truststore.

    Raises
    ------
    subprocess.CalledProcessError
        Raised if the call to :command:`keystore` results in a non-zero
        exit status.
    RuntimeError
        Raised if the truststore is not generated.

    Notes
    -----
    Internally this function calls out to the ``keytool`` command-line tool.
    """
    if password is None:
        password = generate_password()

    with tempfile.TemporaryDirectory() as tempdirname:
        tempdir = Path(tempdirname)

        cert_path = tempdir / "ca.crt"
        cert_path.write_text(cert)

        output_path = tempdir / "client.truststore.jks"

        keytool_args = [
            "keytool",
            "-importcert",
            "-keystore",
            str(output_path),
            "-alias",
            "CARoot",
            "-file",
            str(cert_path),
            "-storepass",
            password,
            "-storetype",
            "jks",
            "-trustcacerts",
            "-noprompt",
        ]
        result = subprocess.run(
            args=keytool_args, capture_output=True, check=True
        )
        if not output_path.is_file():
            _log_result(result)
            raise RuntimeError("truststore was not generated")

        return output_path.read_bytes(), password


@lru_cache(maxsize=128)
def create_keystore(
    user_ca_cert: str,
    user_cert: str,
    user_key: str,
    password: str | None = None,
) -> tuple[bytes, str]:
    """Create a JKS-formatted keystore using the client's CA certificate,
    certificate, and key.

    Parameters
    ----------
    user_ca_cert : `str`
        The content of the KafkaUser's CA certificate.
    user_cert : `str`
        The content of the KafkaUser's certificate.
    user_key : `str`
        The content of the KafkaUser's private key.
    password : `str`, optional
        Password to protect the output keystore with. If not set, a random
        password will be generated.

    Returns
    -------
    keystore_content : `bytes`
        The content of a JKS keystore.
    password : `str`
        The password generated for the keystore.

    Raises
    ------
    subprocess.CalledProcessError
        Raised if the calls to :command:`keystore` or :command:`openssl` result
        in a non-zero exit status.
    RuntimeError
        Raised if the keystore is not generated.

    Notes
    -----
    Internally this function calls out to the ``openssl`` and ``keytool``
    command-line tools.
    """
    if password is None:
        password = generate_password()

    with tempfile.TemporaryDirectory() as tempdirname:
        tempdir = Path(tempdirname)

        user_ca_cert_path = tempdir / "user.ca.crt"
        user_ca_cert_path.write_text(user_ca_cert)

        user_cert_path = tempdir / "user.crt"
        user_cert_path.write_text(user_cert)

        user_key_path = tempdir / "user.key"
        user_key_path.write_text(user_key)

        p12_path = tempdir / "user.p12"
        keystore_path = tempdir / "client.keystore.jks"

        openssl_args = [
            "openssl",
            "pkcs12",
            "-export",
            "-in",
            str(user_cert_path),
            "-inkey",
            str(user_key_path),
            "-chain",
            "-CAfile",
            str(user_ca_cert_path),
            "-name",
            "confluent-schema-registry",
            "-passout",
            f"pass:{password}",
            "-out",
            str(p12_path),
        ]
        openssl_result = subprocess.run(
            args=openssl_args, capture_output=True, check=True
        )
        if not p12_path.is_file():
            _log_result(openssl_result)
            raise RuntimeError("user.p12 not generated by openssl")

        keytool_args = [
            "keytool",
            "-importkeystore",
            "-deststorepass",
            password,
            "-destkeystore",
            str(keystore_path),
            "-deststoretype",
            "jks",
            "-srckeystore",
            str(p12_path),
            "-srcstoretype",
            "PKCS12",
            "-srcstorepass",
            password,
            "-noprompt",
        ]
        keytool_result = subprocess.run(
            args=keytool_args, capture_output=True, check=True
        )
        if not keystore_path.is_file():
            _log_result(keytool_result)
            raise RuntimeError("keystore not generated by keytool")

        return keystore_path.read_bytes(), password


def _log_result(result: Any, logger: Any | None = None) -> None:
    """Log the result of a subprocess.run call for debugging."""
    if logger is None:
        logger = structlog.getLogger(__name__)

    command = result.args[0]
    logger.debug(f"{command} status: {result.returncode}")
    logger.debug(f"{command} args: {' '.join(result.args)}")
    logger.debug(f"{command} stdout:\n{result.stdout.decode('utf-8')}")
    logger.debug(f"{command} stdin:\n{result.stderr.decode('utf-8')}")


def generate_password() -> str:
    """Generate a random password."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for i in range(24))
