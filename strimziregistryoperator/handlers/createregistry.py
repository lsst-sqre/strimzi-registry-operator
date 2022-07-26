"""Kopf handler for the creation of a StrimziSchemaRegistry."""

import kopf

from .. import state
from ..certprocessor import create_secret
from ..deployments import (
    create_deployment,
    create_service,
    get_kafka_bootstrap_server,
)
from ..k8s import create_k8sclient, get_deployment, get_secret, get_service


@kopf.on.create("roundtable.lsst.codes", "v1beta1", "strimzischemaregistries")
def create_registry(spec, meta, namespace, name, uid, logger, body, **kwargs):
    """Handle creation of a StrimziSchemaRegistry resource by deploying a
    new Schema Registry.

    Parameters
    ----------
    spec : dict
        The ``spec`` field of the ``StrimziSchemaRegistry`` custom Kubernetes
        resource.
    meta : dict
        The ``metadata`` field of the ``StrimziSchemaRegistry`` custom
        Kubernetes resource.
    namespace : str
        The Kubernetes namespace of the ``StrimziSchemaRegistry`` custom
        Kubernetes resource.
    uid : str
        The ``metadata.uid`` field of ``StrimziSchemaRegistry``.
    body : dict
        The full body of the ``StrimziSchemaRegistry`` as a read-only dict.
    logger
        The kopf logger.
    """

    k8s_client = create_k8sclient()
    k8s_apps_v1_api = k8s_client.AppsV1Api()
    k8s_cr_api = k8s_client.CustomObjectsApi()
    k8s_core_v1_api = k8s_client.CoreV1Api()

    # Get configurations from StrimziSchemaRegistry
    try:
        strimzi_api_version = spec["strimziVersion"]
    except KeyError:
        try:
            strimzi_api_version = spec["strimzi-version"]
            logger.warning(
                "The strimzi-version configuration is deprecated. "
                "Use strimziVersion instead."
            )
        except KeyError:
            strimzi_api_version = "v1beta2"
            logger.warning(
                "StrimziSchemaRegistry %s is missing a strimziVersion, "
                "using default %s",
                name,
                strimzi_api_version,
            )

    try:
        listener_name = spec["listener"]
    except KeyError:
        listener_name = "tls"
        logger.warning(
            "StrimziSchemaRegistry %s is missing a listener name, "
            "using default %s",
            name,
            listener_name,
        )

    service_type = spec.get("serviceType", "ClusterIP")

    registry_image = spec.get(
        "registryImage", "confluentinc/cp-schema-registry"
    )

    registry_image_tag = spec.get("registryImageTag", "5.3.1")

    logger.info(
        "Creating a new Schema Registry deployment: %s with listener=%s and "
        "strimzi-version=%s serviceType=%s image=%s:%s",
        name,
        listener_name,
        strimzi_api_version,
        service_type,
        registry_image,
        registry_image_tag,
    )

    # Get the name of the Kafka cluster associated with the
    # StrimziSchemaRegistry's associated strimzi KafkaUser resource.
    # The StrimziSchemaRegistry and its KafkaUser have the same name.
    kafkauser = k8s_cr_api.get_namespaced_custom_object(
        group="kafka.strimzi.io",
        version=strimzi_api_version,
        namespace=namespace,
        plural="kafkausers",
        name=name,  # assume StrimziSchemaRegistry name matches
    )
    cluster_name = kafkauser["metadata"]["labels"]["strimzi.io/cluster"]

    # Get the Kafka bootstrap server corresponding to the configured
    # Kafka listener name.
    kafka = k8s_cr_api.get_namespaced_custom_object(
        group="kafka.strimzi.io",
        version=strimzi_api_version,
        namespace=namespace,
        plural="kafkas",
        name=cluster_name,
    )
    bootstrap_server = get_kafka_bootstrap_server(
        kafka, listener_name=listener_name
    )

    # Create the JKS-formatted truststore/keystore secrets
    secret = create_secret(
        kafka_username=name,  # assume the StrimziSchemaRegistry name matches
        namespace=namespace,
        cluster=cluster_name,
        owner=body,
        k8s_client=k8s_client,
        logger=logger,
    )
    secret_name = secret["metadata"]["name"]

    # Get the secret so now it has the resourceVersion metadata
    secret_body = get_secret(
        name=secret_name, namespace=namespace, k8s_client=k8s_client
    )
    secret_version = secret_body["metadata"]["resourceVersion"]

    deployment_exists = False
    service_exists = False

    try:
        get_deployment(name=name, namespace=namespace, k8s_client=k8s_client)
        deployment_exists = True
    except Exception:
        logger.exception("Did not retrieve existing deployment")

    # Create the Schema Registry deployment
    if not deployment_exists:
        dep_body = create_deployment(
            name=name,
            bootstrap_server=bootstrap_server,
            secret_name=secret_name,
            secret_version=secret_version,
            registry_image=registry_image,
            registry_image_tag=registry_image_tag,
        )
        # Set the StrimziSchemaRegistry as the owner
        kopf.adopt(dep_body, owner=body)
        dep_response = k8s_apps_v1_api.create_namespaced_deployment(
            body=dep_body, namespace=namespace
        )
        logger.debug(str(dep_response))
    else:
        logger.info("Deployment already exists")

    try:
        get_service(name=name, namespace=namespace, k8s_client=k8s_client)
        service_exists = True
    except Exception:
        logger.exception("Did not retrieve existing service")

    # Create the http service to access the Schema Registry REST API
    if not service_exists:
        svc_body = create_service(name=name, service_type=service_type)
        # Set the StrimziSchemaRegistry as the owner
        kopf.adopt(svc_body, owner=body)
        svc_response = k8s_core_v1_api.create_namespaced_service(
            body=svc_body, namespace=namespace
        )
        logger.debug(str(svc_response))
    else:
        logger.info("Service already exists")

    # Add the name of the registry to the cache
    state.registry_names.add(name)
