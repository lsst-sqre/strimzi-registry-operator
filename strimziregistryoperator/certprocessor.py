"""Utilities for generating the truststore and keystore for the Schema Registry
based on the cluster's CA cert and the KafkaUser's key.
"""

__all__ = ('create_truststore',)

from pathlib import Path
import subprocess
import tempfile


def create_truststore(cert, password):
    """Create a JKS-formatted truststore using the cluster's CA certificate.

    Parameters
    ----------
    cert : `str`
        The content of the Kafka cluster CA certificate. You can get this from
        a Kubernetes Secret named ``<cluster>-cluster-ca-cert``, and
        specifially the secret key named ``ca.crt``.
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
            print(f'keytool status: {result.returncode}')
            print(f'keytool args: {" ".join(result.args)}')
            print(f'keytool stdout:\n{result.stdout.decode("utf-8")}')
            print(f'keytool stdin:\n{result.stderr.decode("utf-8")}')
            raise RuntimeError('truststore was not generated')

        return output_path.read_bytes()
