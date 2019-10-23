"""Kopf handler to react to changes to Strimzi-generated Kubernetes secrets
for the cluster CA certificate or the client certificates.
"""

__all__ = ('handle_secret_change', 'refresh_with_new_cluster_ca',
           'refresh_with_new_client_secret')

import kopf

from ..k8stools import create_k8sclient
from ..certprocessor import create_secret
from .. import state


@kopf.on.event('', 'v1', 'secrets')
def handle_secret_change(spec, meta, namespace, name, uid, event, body, logger,
                         **kwargs):
    logger.info(f'Detected secret change: "{name}" ({event["type"]})')

    # Act only on Secrets that have been created or updated
    # FIXME check these event names
    if event['type'] not in ('create', 'update'):
        return

    # Act only on Secrets with the matching strimzi.io/cluster configuration.
    try:
        if meta['labels']['strimzi.io/cluster'] != state.cluster_name:
            return
    except KeyError:
        # didn't have a strimzio.io/cluster key; so no action is needed.
        return

    if name == f'{state.cluster_name}-cluster-ca-cert':
        # Handle a change in the cluster CA certificate
        refresh_with_new_cluster_ca(
            cluster_ca_body=body,
            namespace=namespace,
            logger=logger)
    elif name in state.registry_names:
        # Handle a change in the KafkaUser client certificate of a
        # StrimziSchemaRegistry
        refresh_with_new_client_secret(
            kafkauser_secret=body,
            namespace=namespace,
            logger=logger
        )


def refresh_with_new_cluster_ca(*, cluster_ca_secret, namespace, logger):
    k8s_client = create_k8sclient()

    # Iterate over each managed registry...
    for registry_name in state.registry_names:
        cluster = cluster_ca_secret['metadata']['labels']['strimzi.io/cluster']

        create_secret(
            registry_name=registry_name,
            namespace=namespace,
            cluster=cluster,
            k8s_client=k8s_client,
            cluster_ca_secret=cluster_ca_secret
        )

        # TODO now restart the schema registry pods


def refresh_with_new_client_secret(*, kafkauser_secret, namespace, logger):
    k8s_client = create_k8sclient()

    registry_name = kafkauser_secret['metadata']['name']
    cluster = kafkauser_secret['metadata']['labels']['strimzi.io/cluster']

    create_secret(
        registry_name=registry_name,
        namespace=namespace,
        cluster=cluster,
        k8s_client=k8s_client,
        client_secret=kafkauser_secret
    )

    # TODO now restart the schema registry pods
