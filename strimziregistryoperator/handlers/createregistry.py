"""Kopf handler for the creation of a StrimziSchemaRegistry.
"""

import kopf

from ..k8s import create_k8sclient, get_deployment, get_service, get_secret
from ..certprocessor import create_secret
from ..deployments import (get_cluster_internal_listener, create_deployment,
                           create_service)
from .. import state


@kopf.on.create('roundtable.lsst.codes', 'v1beta1', 'strimzischemaregistries')
def create_registry(spec, meta, namespace, name, uid, logger, body, **kwargs):
    """Handle creation of a StrimziSchemaRegistry resource by deploying a
    new Schema Registry.
    """
    logger.info(f'Creating a new registry deployment: "{name}"')

    k8s_client = create_k8sclient()
    k8s_apps_v1_api = k8s_client.AppsV1Api()
    k8s_cr_api = k8s_client.CustomObjectsApi()
    k8s_core_v1_api = k8s_client.CoreV1Api()

    strimzi_version = spec.get("strimzi-version", "v1beta1")
    # Pull the KafkaUser resource so we can get the cluster name
    kafkauser = k8s_cr_api.get_namespaced_custom_object(
        group='kafka.strimzi.io',
        version=strimzi_version,
        namespace=namespace,
        plural='kafkausers',
        name=name  # assume StrimziSchemaRegistry name matches
    )
    cluster_name = kafkauser['metadata']['labels']['strimzi.io/cluster']

    # Pull the Kafka resource so we can get the listener
    kafka = k8s_cr_api.get_namespaced_custom_object(
        group='kafka.strimzi.io',
        version=strimzi_version,
        namespace=namespace,
        plural='kafkas',
        name=cluster_name
    )

    bootstrap_server = get_cluster_internal_listener(kafka)

    # Create the JKS-formatted truststore/keystore secrets
    secret = create_secret(
        kafka_username=name,  # assume the StrimziSchemaRegistry name matches
        namespace=namespace,
        cluster=cluster_name,
        owner=body,
        k8s_client=k8s_client,
        logger=logger
    )
    secret_name = secret['metadata']['name']

    # Get the secret so now it has the resourceVersion metadata
    secret_body = get_secret(
        name=secret_name,
        namespace=namespace,
        k8s_client=k8s_client)
    secret_version = secret_body['metadata']['resourceVersion']

    deployment_exists = False
    service_exists = False

    try:
        get_deployment(
            name=name,
            namespace=namespace,
            k8s_client=k8s_client)
        deployment_exists = True
    except Exception:
        logger.exception('Did not retrieve existing deployment')

    # Create the Schema Registry deployment
    if not deployment_exists:
        dep_body = create_deployment(
            name=name,
            bootstrap_server=bootstrap_server,
            secret_name=secret_name,
            secret_version=secret_version)
        # Set the StrimziSchemaRegistry as the owner
        kopf.adopt(dep_body, owner=body)
        dep_response = k8s_apps_v1_api.create_namespaced_deployment(
            body=dep_body,
            namespace=namespace
        )
        logger.debug(str(dep_response))
    else:
        logger.info('Deployment already exists')

    try:
        get_service(
            name=name,
            namespace=namespace,
            k8s_client=k8s_client)
        service_exists = True
    except Exception:
        logger.exception('Did not retrieve existing service')

    # Create the http service to access the Schema Registry REST API
    if not service_exists:
        svc_body = create_service(
            name=name)
        # Set the StrimziSchemaRegistry as the owner
        kopf.adopt(svc_body, owner=body)
        svc_response = k8s_core_v1_api.create_namespaced_service(
            body=svc_body,
            namespace=namespace
        )
        logger.debug(str(svc_response))
    else:
        logger.info('Service already exists')

    # Add the name of the registry to the cache
    state.registry_names.add(name)
