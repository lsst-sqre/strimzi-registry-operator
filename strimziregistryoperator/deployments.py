"""Utilities for creating deployments and related resources.
"""

__all__ = ('get_cluster_listener', 'create_deployment', 'create_service')

import kopf


def get_cluster_listener(kafka, listener_name="tls"):
    """Get a listener by name from a Kafka cluster deployment.
    """
    try:
        listeners = kafka['status']['listeners']
    except KeyError:
        raise kopf.TemporaryError(
            'Could not get status.listeners from Kafka resource.',
            delay=10,
        )

    for listener in listeners:
        try:
            # For various historical reasons, the 'name' of the listener is
            # called 'type' in the status field of a Kafka resource from
            # Strimzi.
            if listener['type'] == listener_name:
                # Convenience field available in some versions of Strimzi.
                if "bootstrapServers" in listener:
                    return listener["bootstrapServers"]

                # fall back to constructing it ourselves from the first address
                # on the listener, which should usually work.
                else:
                    address = listener['addresses'][0]
                    return f'{address["host"]}:{address["port"]}'
        except (KeyError, IndexError):
            continue

    all_names = [listener.get('type') for listener in listeners]
    msg = (
        f'Could not find address of a listener named {listener_name} '
        f'from the Kafka resource. Available names: {all_names}'
    )
    raise kopf.TemporaryError(msg, delay=10)


def create_deployment(*, name, bootstrap_server, secret_name, secret_version):
    """Create the JSON resource for a Deployment of the Confluence Schema
    Registry.

    Parameters
    ----------
    name : `str`
        Name of the StrimziKafkaUser, which is also used as the name of the
        deployment.
    bootstrap_server : `str`
        The ``host:port`` of the Kafka bootstrap service. See
        `get_cluster_tls_listener`.
    secret_name : `str`
        Name of the Secret resource containing the JKS-formatted keystore
        and truststore.
    secret_version : `str`
        The ``resourceVersion`` of the Secret containing the JKS-formatted
        keystore and truststore.

    Returns
    -------
    deployment : `dict`
        The Deployment resource.
    """
    key_prefix = 'strimziregistryoperator.roundtable.lsst.codes'

    registry_container = create_container_spec(
        secret_name=secret_name,
        bootstrap_server=bootstrap_server)

    # The pod template
    template = {
        'metadata': {
            'labels': {'app': name},
            'annotations': {
                f'{key_prefix}/jksVersion': secret_version
            }
        },
        'spec': {
            'containers': [registry_container],
            'volumes': [
                {
                    'name': 'tls',
                    'secret': {'secretName': secret_name}
                }
            ]
        }
    }

    dep = {
        'apiVersion': 'apps/v1',
        'kind': 'Deployment',
        'metadata': {
            'name': name,
            'labels': {'app': name}
        },
        'spec': {
            'replicas': 1,
            'selector': {
                'matchLabels': {'app': name}
            },
            'template': template}
    }

    return dep


def create_container_spec(*, secret_name, bootstrap_server):
    """Create the container spec for the Schema Registry deployment.
    """
    registry_env = [
        {
            'name': 'SCHEMA_REGISTRY_HOST_NAME',
            'valueFrom': {
                'fieldRef': {
                    'fieldPath': 'status.podIP'
                }
            }
        },
        {
            'name': 'SCHEMA_REGISTRY_LISTENERS',
            'value': 'http://0.0.0.0:8081'
        },
        {
            'name': 'SCHEMA_REGISTRY_KAFKASTORE_BOOTSTRAP_SERVERS',
            'value': bootstrap_server
        },
        # NOTE: This can likely be left to the default
        # {
        #     'name': 'SCHEMA_REGISTRY_KAFKASTORE_GROUP_ID',
        #     'value': None,  # FIXME
        # },
        {
            'name': 'SCHEMA_REGISTRY_AVRO_COMPATIBILITY_LEVEL',
            'value': 'forward'
        },
        {
            'name': 'SCHEMA_REGISTRY_MASTER_ELIGIBILITY',
            'value': 'true'
        },
        {
            'name': 'SCHEMA_REGISTRY_HEAP_OPTS',
            'value': '-Xms512M -Xmx512M',
        },
        {
            'name': 'SCHEMA_REGISTRY_KAFKASTORE_TOPIC',
            'value': 'registry-schemas'
        },
        {
            'name': 'SCHEMA_REGISTRY_KAFKASTORE_SSL_KEYSTORE_LOCATION',
            'value': '/var/schemaregistry/keystore.jks'
        },
        {
            'name': 'SCHEMA_REGISTRY_KAFKASTORE_SSL_KEYSTORE_PASSWORD',
            'valueFrom': {'secretKeyRef': {'name': secret_name,
                                           'key': 'keystore_password'}}
        },
        {
            'name': 'SCHEMA_REGISTRY_KAFKASTORE_SSL_TRUSTSTORE_LOCATION',
            'value': '/var/schemaregistry/truststore.jks'
        },
        {
            'name': 'SCHEMA_REGISTRY_KAFKASTORE_SSL_TRUSTSTORE_PASSWORD',
            'valueFrom': {'secretKeyRef': {'name': secret_name,
                                           'key': 'truststore_password'}}
        },
        {
            'name': 'SCHEMA_REGISTRY_KAFKASTORE_SECURITY_PROTOCOL',
            'value': 'SSL'
        }
    ]

    registry_container = {
        'name': 'server',
        'image': 'confluentinc/cp-schema-registry:5.3.1',
        'imagePullPolicy': 'IfNotPresent',
        'ports': [
            {
                'name': 'schema-registry',
                'containerPort': 8081,
                'protocol': 'TCP'
            }
        ],
        'env': registry_env,
        'volumeMounts': [
            {
                'mountPath': '/var/schemaregistry',
                'name': 'tls',
                'readOnly': True
            }
        ]
    }

    return registry_container


def create_service(*, name):
    """Create a Service resource for the Schema Registry.

    Parameters
    ----------
    name : `str`
        Name of the StrimziKafkaUser, which is also used as the name of the
        deployment.

    Returns
    -------
    service : `dict`
        The Service resource.
    """
    s = {
        'apiVersion': 'v1',
        'kind': 'Service',
        'metadata': {
            'name': name,
            'labels': {
                'name': name
            }
        },
        'spec': {
            'ports': [
                {
                    'name': 'schema-registry',
                    'port': 8081
                }
            ],
            'selector': {
                'app': name,
            }
        }
    }

    return s


def update_deployment(*, deployment, secret_version, k8s_client,
                      name, namespace):
    """Update the schema registry deploymeent with a new Secret version
    to trigger a refresh of all its pods.
    """
    key_prefix = 'strimziregistryoperator.roundtable.lsst.codes'
    secret_version_key = f'{key_prefix}/jksVersion'
    deployment.metadata.annotations[secret_version_key] = secret_version

    apps_api = k8s_client.AppsV1Api()
    apps_api.patch_namespaced_deployment(
        name=name,
        namespace=namespace,
        body=deployment)
