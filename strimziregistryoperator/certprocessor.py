"""Utilities for generating the truststore and keystore for the Schema Registry
based on the cluster's CA cert and the KafkaUser's key.
"""

__all__ = ('create_secret', 'get_cluster_ca_secret', 'get_client_secret',
           'create_truststore', 'create_keystore')

import base64
from functools import lru_cache
from pathlib import Path
import subprocess
import string
import secrets
import tempfile


def create_secret(*, registry_name, namespace, cluster, k8s_client,
                  cluster_ca_secret=None, client_secret=None):
    """Create and deploy a new Secret for the StrimziSchemaRegistry with
    JKS-formatted key and truststores.

    Parameters
    ----------
    registry_name : `str`
        Name of the associated StrimziSchemaRegistry.
    namespace : `str`
        The name of the Kubernetes namespace where the Strimzi Kafka cluster
        operates.
    cluster : `str`
        The name of the Strimzi Kafka cluster.
    k8s_client
        A Kubernetes client (see
        `strimziregistryoperator.k8stools.create_k8sclient`).
    cluster_ca_secret : `dict`, optional
        The Kubernetes Secret resource body for the cluster CA secret,
        named ``<cluster>-cluster-ca-cert``. If not set, the resource will be
        automatically retrieved for you.
    client_secret : `dict`, optional
        The Kubernetes secret resource created by Strimzi with the certificates
        for the KafkaUser. This secret is named after ``registry_name``. If
        not set, this resource will be retrieved automatically for you.
    """
    if cluster_ca_secret is None:
        cluster_ca_secret = get_cluster_ca_secret(
            namespace=namespace, cluster=cluster, k8s_client=k8s_client)
    cluster_secret_version = cluster_ca_secret['metadata']['resourceVersion']
    cluster_ca_cert = decode_secret_field(
        cluster_ca_secret['data']['ca.crt'])

    if client_secret is None:
        client_secret = get_client_secret(
            namespace=namespace, username=registry_name, k8s_client=k8s_client)
    client_secret_version = client_secret['metadata']['resourceVersion']
    client_ca_cert = decode_secret_field(
        client_secret['data']['ca.crt'])
    client_cert = decode_secret_field(
        client_secret['data']['user.crt'])
    client_key = decode_secret_field(
        client_secret['data']['user.key'])

    truststore, truststore_password = create_truststore(cluster_ca_cert)
    keystore, keystore_password = create_keystore(client_ca_cert, client_cert,
                                                  client_key)

    api_instance = k8s_client.CoreV1Api()
    secret = k8s_client.V1Secret()
    secret.metadata = k8s_client.V1ObjectMeta(name=f'{registry_name}-jks')
    secret.metadata.annotations = {
        'strimziregistryoperator.roundtable.lsst.codes/caSecretVersion':
            cluster_secret_version,
        'strimziregistryoperator.roundtable.lsst.codes/clientSecretVersion':
            client_secret_version,
    }
    secret.type = "Opaque"
    secret.data = {
        "truststore.jks": base64.b64encode(truststore),
        "keystore.jks": base64.b64encode(keystore),
        "truststore_password": base64.b64encode(
            truststore_password.encode('utf-8')),
        "keystore_password": base64.b64encode(
            keystore_password.encode('utf-8')),
    }

    api_instance.create_namespaced_secret(namespace=namespace, body=secret)


def get_cluster_ca_secret(*, namespace, cluster, k8s_client):
    """Get the cluster's CA cert Secret (named ``<cluster>-cluster-ca-cert``).

    Parameters
    ----------
    namespace : `str`
        The Kubernetes namespace where the Strimzi Kafka cluster operates.
    cluster : `str`
        The name of the Strimzi Kafka cluster.
    k8s_client
        A Kubernetes client (see
        `strimziregistryoperator.k8stools.create_k8sclient`).

    Returns
    -------
    secret : `dict`
        The Kubernetes Secret resource.
    """
    v1_api = k8s_client.CoreV1Api()
    name = f'{cluster}-cluster-ca-cert'
    return v1_api.read_namespaced_secret(name, namespace)


def get_client_secret(*, namespace, username, k8s_client):
    """Get the Secret resource created by Strimzi for a KafkaUser.

    Parameters
    ----------
    namespace : `str`
        The Kubernetes namespace where the Strimzi Kafka cluster operates.
    username : `str`
        The name of the KafkaUser, which is also the name of its corresponding
        Secret resource created by the Strimzi user operator.
    k8s_client
        A Kubernetes client (see
        `strimziregistryoperator.k8stools.create_k8sclient`).

    Returns
    -------
    secret : `dict`
        The Kubernetes Secret resource.
    """
    v1_api = k8s_client.CoreV1Api()
    return v1_api.read_namespaced_secret(username, namespace)


def decode_secret_field(value):
    return base64.b64decode(value).decode('utf-8')


@lru_cache(maxsize=128)
def create_truststore(cert, password=None):
    """Create a JKS-formatted truststore using the cluster's CA certificate.

    Parameters
    ----------
    cert : `str`
        The content of the Kafka cluster CA certificate. You can get this from
        a Kubernetes Secret named ``<cluster>-cluster-ca-cert``, and
        specifially the secret key named ``ca.crt``. See
        `get_cluster_ca_cert`.

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

        cert_path = tempdir / 'ca.crt'
        cert_path.write_text(cert)

        output_path = tempdir / 'client.truststore.jks'

        keytool_args = [
            'keytool',
            '-importcert',
            '-keystore',
            str(output_path),
            '-alias',
            'CARoot',
            '-file',
            str(cert_path),
            '-storepass',
            password,
            '-trustcacerts',
            '-noprompt'
        ]
        result = subprocess.run(
            args=keytool_args,
            capture_output=True,
            check=True)
        if not output_path.is_file():
            _print_result(result)
            raise RuntimeError('truststore was not generated')

        return output_path.read_bytes(), password


@lru_cache(maxsize=128)
def create_keystore(user_ca_cert, user_cert, user_key, password=None):
    """Create a JKS-formatted keystore using the client's CA certificate,
    certificate, and key.

    Parameters
    ----------
    user_ca_cert : `str`
        The content of the KafkaUser's CA certificate. You can get this from
        the Kubernetes Secret named after the KafkaUser and specifically the
        ``ca.crt`` field. See the `get_user_certs` function.
    user_cert : `str`
        The content of the KafkaUser's certificate. You can get this from
        the Kubernetes Secret named after the KafkaUser and specifically the
        ``user.crt`` field. See the `get_user_certs` function.
    user_key : `str`
        The content of the KafkaUser's private key. You can get this from
        the Kubernetes Secret named after the KafkaUser and specifically the
        ``user.key`` field. See the `get_user_certs` function.

    Returns
    -------
    keytore_content : `bytes`
        The content of a JKS keystore.
    password : `str`
        Password to protect the output keystore (``keystore_content``)
        with.

    Raises
    ------
    subprocess.CalledProcessError
        Raised if the calls to :command:`keystore` or :command:`openssl` result
        in a non-zero exit status.
    RuntimeError
        Raised if the truststore is not generated.

    Notes
    -----
    Internally this function calls out to the ``openssl`` and ``keytool``
    command-line tool.
    """
    if password is None:
        password = generate_password()

    with tempfile.TemporaryDirectory() as tempdirname:
        tempdir = Path(tempdirname)

        user_ca_cert_path = tempdir / 'user.ca.crt'
        user_ca_cert_path.write_text(user_ca_cert)

        user_cert_path = tempdir / 'user.crt'
        user_cert_path.write_text(user_cert)

        user_key_path = tempdir / 'user.key'
        user_key_path.write_text(user_key)

        p12_path = tempdir / 'user.p12'
        keystore_path = tempdir / 'client.keystore.jks'

        openssl_args = [
            'openssl',
            'pkcs12',
            '-export',
            '-in',
            str(user_cert_path),
            '-inkey',
            str(user_key_path),
            '-chain',
            '-CAfile',
            str(user_ca_cert_path),
            '-name',
            'confluent-schema-registry',
            '-passout',
            f'pass:{password}',
            '-out',
            str(p12_path)
        ]
        openssl_result = subprocess.run(
            args=openssl_args,
            capture_output=True,
            check=True
        )
        if not p12_path.is_file():
            _print_result(openssl_result)
            raise RuntimeError('user.p12 not generated by openssl')

        keytool_args = [
            'keytool',
            '-importkeystore',
            '-deststorepass',
            password,
            '-destkeystore',
            str(keystore_path),
            '-srckeystore',
            str(p12_path),
            '-srcstoretype',
            'PKCS12',
            '-srcstorepass',
            password,
            '-noprompt'
        ]
        keytool_result = subprocess.run(
            args=keytool_args,
            capture_output=True,
            check=True
        )
        if not keystore_path.is_file():
            _print_result(keytool_result)
            raise RuntimeError('keystore not generated by keytool')

        return keystore_path.read_bytes(), password


def _print_result(result):
    command = result.args[0]
    print(f'{command} status: {result.returncode}')
    print(f'{command} args: {" ".join(result.args)}')
    print(f'{command} stdout:\n{result.stdout.decode("utf-8")}')
    print(f'{command} stdin:\n{result.stderr.decode("utf-8")}')


def generate_password():
    """Generate a random password.
    """
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for i in range(24))
