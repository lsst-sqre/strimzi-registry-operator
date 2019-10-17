"""Utilities for generating the truststore and keystore for the Schema Registry
based on the cluster's CA cert and the KafkaUser's key.
"""

__all__ = ('get_cluster_ca_cert', 'get_user_certs', 'create_truststore',
           'create_keystore')

import base64
from pathlib import Path
import subprocess
import tempfile


def get_cluster_ca_cert(*, namespace, cluster, k8s_client):
    """Get the cluster's CA cert from the ``<cluster>-cluster-ca-cert``
    Kubernetes secret.

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
    cert : `str`
        The decoded contents of the CA cert. This can be passed to the
        `create_truststore` function.
    """
    v1_api = k8s_client.CoreV2Api()
    name = f'{cluster}-cluster-ca-cert'
    secret = v1_api.read_namespaced_secret(name, namespace)
    return base64.b64decode(secret.data['ca.crt']).decode('utf-8')


def get_user_certs(*, namespace, username, k8s_client):
    """Get the KafkaUser's certificates and key from its corresponding
    Kubernetes secret.

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
    certs : `dict`
        A dictionary with the decoded (`str`) contents of the certs and
        private key. The dictionary key names are:

        - ``'ca.crt'``
        - ``'user.crt'``
        - ``'user.key'``

        These can be passed to the `create_keystore` function.
    """
    v1_api = k8s_client.CoreV2Api()
    secret = v1_api.read_namespaced_secret(username, namespace)
    return {k: base64.b64decode(secret.data[k]).decode('utf-8')
            for k in ('ca.crt', 'user.crt', 'user.key')}


def create_truststore(cert, password):
    """Create a JKS-formatted truststore using the cluster's CA certificate.

    Parameters
    ----------
    cert : `str`
        The content of the Kafka cluster CA certificate. You can get this from
        a Kubernetes Secret named ``<cluster>-cluster-ca-cert``, and
        specifially the secret key named ``ca.crt``. See
        `get_cluster_ca_cert`.
    password : `str`
        Password to protect the output truststore (``truststore_content``)
        with.

    Returns
    -------
    truststore_content : `bytes`
        The content of a JKS truststore containing the cluster CA certificate.

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

        return output_path.read_bytes()


def create_keystore(user_ca_cert, user_cert, user_key, password):
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
    password : `str`
        Password to protect the output keystore (``keystore_content``)
        with.

    Returns
    -------
    keytore_content : `bytes`
        The content of a JKS keystore.

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

        return keystore_path.read_bytes()


def _print_result(result):
    command = result.args[0]
    print(f'{command} status: {result.returncode}')
    print(f'{command} args: {" ".join(result.args)}')
    print(f'{command} stdout:\n{result.stdout.decode("utf-8")}')
    print(f'{command} stdin:\n{result.stderr.decode("utf-8")}')
