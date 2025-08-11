"""Kopf handler for the creation of a StrimziSchemaRegistry."""

__all__ = (
    "create_registry",
    "create_registry_resources",
    "get_nullable",
    "parse_registry_spec",
    "register_registry_name",
)

from typing import Any, cast

import kopf

from strimziregistryoperator.certprocessor import create_secret
from strimziregistryoperator.deployments import (
    create_deployment,
    create_service,
    get_kafka_bootstrap_server,
)
from strimziregistryoperator.k8s import (
    create_k8sclient,
    get_deployment,
    get_secret,
    get_service,
)
from strimziregistryoperator.state import registry_names


@kopf.on.create("roundtable.lsst.codes", "v1beta1", "strimzischemaregistries")  # type: ignore[arg-type]
def create_registry(
    *,
    spec: dict[str, Any],
    meta: dict[str, Any],
    namespace: str,
    name: str,
    uid: str,
    logger: Any,
    body: dict[str, Any],
    **kwargs: Any,
) -> None:
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
    name : str
        The name of the ``StrimziSchemaRegistry`` custom Kubernetes resource.
    uid : str
        The ``metadata.uid`` field of ``StrimziSchemaRegistry``.
    logger : Any
        The kopf logger.
    body : dict
        The full body of the ``StrimziSchemaRegistry`` as a read-only dict.
    **kwargs : Any
        Additional keyword arguments provided by kopf.
    """
    config = parse_registry_spec(spec, name, logger)
    k8s_client = create_k8sclient()
    create_registry_resources(
        name=name,
        namespace=namespace,
        strimzi_api_version=config["strimzi_api_version"],
        listener_name=config["listener_name"],
        k8s_client=k8s_client,
        body=body,
        logger=logger,
        config=config,
    )
    register_registry_name(name)


def parse_registry_spec(
    spec: dict[str, Any], name: str, logger: Any
) -> dict[str, Any]:
    """Parse the spec of a StrimziSchemaRegistry and return the configuration.

    Parameters
    ----------
    spec : dict
        The ``spec`` field of the ``StrimziSchemaRegistry`` custom Kubernetes
        resource.
    name : str
        The name of the ``StrimziSchemaRegistry`` custom Kubernetes resource.
    logger : Any
        The kopf logger.

    Returns
    -------
    dict
        A dictionary containing the configuration for the Schema Registry.
    """
    strimzi_api_version = spec.get("strimziVersion", "v1beta2")
    if "strimziVersion" not in spec:
        logger.warning(
            f"StrimziSchemaRegistry {name} is missing a strimziVersion,"
            f"using  {strimzi_api_version}."
        )

    listener_name = spec.get("listener", "tls")
    if "listener" not in spec:
        logger.warning(
            f"StrimziSchemaRegistry {name} is missing a listener name,"
            f"using {listener_name}."
        )

    return {
        "strimzi_api_version": strimzi_api_version,
        "listener_name": listener_name,
        "service_type": spec.get("serviceType", "ClusterIP"),
        "registry_image": spec.get(
            "registryImage", "confluentinc/cp-schema-registry"
        ),
        "registry_image_tag": spec.get("registryImageTag", "8.0.0"),
        "registry_replicas": spec.get("replicas", 1),
        "registry_cpu_limit": get_nullable(spec, "cpuLimit"),
        "registry_cpu_request": get_nullable(spec, "cpuRequest"),
        "registry_mem_limit": get_nullable(spec, "memoryLimit"),
        "registry_mem_request": get_nullable(spec, "memoryRequest"),
        "registry_compatibility_level": spec.get(
            "compatibilityLevel", "forward"
        ),
        "security_protocol": spec.get("securityProtocol", "SSL"),
    }


def get_nullable(spec: dict[str, str], key: str) -> str | None:
    """Get a value from the spec, returning None if it is not set or empty.

    Parameters
    ----------
    spec : dict
        The spec dictionary from the StrimziSchemaRegistry resource.
    key : str
        The key to look for in the spec dictionary.

    Returns
    -------
    str | None
        The value associated with the key, or None if it is not set or empty.
    """
    value = spec.get(key)
    return None if value in (None, "") else value


def create_registry_resources(
    name: str,
    namespace: str,
    strimzi_api_version: str,
    listener_name: str,
    k8s_client: Any,
    body: dict[str, Any],
    logger: Any,
    config: dict[str, Any],
) -> None:
    """Create the Kubernetes resources for a StrimziSchemaRegistry.

    Parameters
    ----------
    name : str
        The name of the StrimziSchemaRegistry resource.
    namespace : str
        The namespace in which to create the resources.
    strimzi_api_version : str
        The API version of the Strimzi resources.
    listener_name : str
        The name of the Kafka listener to use for the Schema Registry.
    k8s_client : Any
        The Kubernetes client to use for creating resources.
    body : dict[str, Any]
        The full body of the StrimziSchemaRegistry resource.
    logger : Any
        The kopf logger.
    config : dict[str, Any]
        The configuration dictionary containing settings for the
        Schema Registry.
    """
    k8s_apps_v1_api = k8s_client.AppsV1Api()
    k8s_core_v1_api = k8s_client.CoreV1Api()
    k8s_cr_api = k8s_client.CustomObjectsApi()

    # Get the name of the Kafka cluster associated with the
    # StrimziSchemaRegistry's associated strimzi KafkaUser resource.
    # The StrimziSchemaRegistry and its KafkaUser have the same name.
    kafkauser = k8s_cr_api.get_namespaced_custom_object(
        group="kafka.strimzi.io",
        version=strimzi_api_version,
        namespace=namespace,
        plural="kafkausers",
        name=name,
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
        kafka_username=name,
        namespace=namespace,
        cluster=cluster_name,
        owner=cast("kopf.Body", body),
        k8s_client=k8s_client,
        logger=logger,
    )
    secret_name = secret["metadata"]["name"]

    # Get the secret so now it has the resourceVersion metadata
    secret_version = get_secret(
        name=secret_name,
        namespace=namespace,
        k8s_client=k8s_client,
    )["metadata"]["resourceVersion"]

    # Create the Schema Registry deployment
    try:
        get_deployment(name=name, namespace=namespace, k8s_client=k8s_client)
        logger.info("Deployment already exists")
    except Exception:
        dep_body = create_deployment(
            name=name,
            bootstrap_server=bootstrap_server,
            secret_name=secret_name,
            secret_version=secret_version,
            registry_image=config["registry_image"],
            registry_image_tag=config["registry_image_tag"],
            registry_replicas=config["registry_replicas"],
            registry_cpu_limit=config["registry_cpu_limit"],
            registry_cpu_request=config["registry_cpu_request"],
            registry_mem_limit=config["registry_mem_limit"],
            registry_mem_request=config["registry_mem_request"],
            compatibility_level=config["registry_compatibility_level"],
            security_protocol=config["security_protocol"],
        )
        # Set the StrimziSchemaRegistry as the owner
        kopf.adopt(dep_body, owner=cast("kopf.Body", body))
        k8s_apps_v1_api.create_namespaced_deployment(
            body=dep_body, namespace=namespace
        )

    # Create the http service to access the Schema Registry REST API
    try:
        get_service(name=name, namespace=namespace, k8s_client=k8s_client)
        logger.info("Service already exists")
    except Exception:
        svc_body = create_service(
            name=name, service_type=config["service_type"]
        )
        kopf.adopt(svc_body, owner=cast("kopf.Body", body))
        k8s_core_v1_api.create_namespaced_service(
            body=svc_body, namespace=namespace
        )


def register_registry_name(name: str) -> None:
    """Add the name of the registry to the cache."""
    registry_names.add(name)
