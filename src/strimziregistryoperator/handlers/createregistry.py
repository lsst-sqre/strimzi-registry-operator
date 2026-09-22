"""Kopf handler for the creation of a StrimziSchemaRegistry."""

__all__ = (
    "create_registry",
    "create_registry_resources",
    "delete_registry",
    "get_nullable",
    "parse_registry_spec",
    "reconcile_pod_disruption_budget",
    "register_registry_name",
    "resume_registry",
    "update_registry_group_id",
    "update_registry_replicas",
)

from collections.abc import Callable
from typing import Any, cast

import kopf
from kubernetes.client.exceptions import ApiException

from strimziregistryoperator import state
from strimziregistryoperator.certprocessor import create_secret
from strimziregistryoperator.deployments import (
    create_deployment,
    create_pod_disruption_budget,
    create_service,
    get_cluster_name,
    get_kafka_bootstrap_server,
    update_deployment_group_id,
    update_deployment_replicas,
)
from strimziregistryoperator.k8s import (
    create_k8sclient,
    get_deployment,
    get_pod_disruption_budget,
    get_secret,
    get_service,
)


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
    cluster_name = get_cluster_name(body)
    if cluster_name is None:
        raise kopf.PermanentError(
            "Missing required label strimzi.io/cluster on "
            "StrimziSchemaRegistry."
        )
    if cluster_name != state.cluster_name:
        logger.info(
            f"Ignoring StrimziSchemaRegistry {name} for Kafka cluster "
            f"{cluster_name}."
        )
        return

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


@kopf.on.delete(
    "roundtable.lsst.codes",
    "v1beta1",
    "strimzischemaregistries",
    optional=True,
)
def delete_registry(*, name: str, **kwargs: Any) -> None:
    """Remove a deleted StrimziSchemaRegistry from the local cache."""
    state.registry_names.discard(name)


@kopf.on.update(  # type: ignore[arg-type]
    "roundtable.lsst.codes",
    "v1beta1",
    "strimzischemaregistries",
    field="spec.groupId",
)
def update_registry_group_id(
    *,
    spec: dict[str, Any],
    namespace: str,
    name: str,
    logger: Any,
    body: dict[str, Any],
    **kwargs: Any,
) -> None:
    """Update the group ID on an existing Schema Registry deployment."""
    cluster_name = get_cluster_name(body)
    if cluster_name is None:
        raise kopf.PermanentError(
            "Missing required label strimzi.io/cluster on "
            "StrimziSchemaRegistry."
        )
    if cluster_name != state.cluster_name:
        logger.info(
            f"Ignoring StrimziSchemaRegistry {name} for Kafka cluster "
            f"{cluster_name}."
        )
        return

    k8s_client = create_k8sclient()
    update_deployment_group_id(
        group_id=spec.get("groupId", "schema-registry"),
        k8s_client=k8s_client,
        name=name,
        namespace=namespace,
    )


@kopf.on.update(  # type: ignore[arg-type]
    "roundtable.lsst.codes",
    "v1beta1",
    "strimzischemaregistries",
    field="spec.replicas",
)
def update_registry_replicas(
    *,
    spec: dict[str, Any],
    namespace: str,
    name: str,
    logger: Any,
    body: dict[str, Any],
    **kwargs: Any,
) -> None:
    """Update replicas and disruption protection for a Schema Registry."""
    _reconcile_registry_availability(
        spec=spec,
        name=name,
        namespace=namespace,
        body=body,
        logger=logger,
    )


@kopf.on.resume(  # type: ignore[arg-type]
    "roundtable.lsst.codes", "v1beta1", "strimzischemaregistries"
)
def resume_registry(
    *,
    spec: dict[str, Any],
    namespace: str,
    name: str,
    logger: Any,
    body: dict[str, Any],
    **kwargs: Any,
) -> None:
    """Restore replica and disruption-budget state when the operator starts."""
    _reconcile_registry_availability(
        spec=spec,
        namespace=namespace,
        name=name,
        logger=logger,
        body=body,
    )


def _reconcile_registry_availability(
    *,
    spec: dict[str, Any],
    namespace: str,
    name: str,
    logger: Any,
    body: dict[str, Any],
) -> None:
    """Reconcile replicas and disruption protection for a registry."""
    cluster_name = get_cluster_name(body)
    if cluster_name is None:
        raise kopf.PermanentError(
            "Missing required label strimzi.io/cluster on "
            "StrimziSchemaRegistry."
        )
    if cluster_name != state.cluster_name:
        logger.info(
            f"Ignoring StrimziSchemaRegistry {name} for Kafka cluster "
            f"{cluster_name}."
        )
        return

    replicas = get_registry_replicas(spec, name)
    k8s_client = create_k8sclient()
    update_deployment_replicas(
        replicas=replicas,
        k8s_client=k8s_client,
        name=name,
        namespace=namespace,
    )
    reconcile_pod_disruption_budget(
        replicas=replicas,
        name=name,
        namespace=namespace,
        k8s_client=k8s_client,
        body=body,
        logger=logger,
    )


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
            f"StrimziSchemaRegistry {name} is missing a strimziVersion, "
            f"using  {strimzi_api_version}."
        )

    listener_name = spec.get("listener", "tls")
    if "listener" not in spec:
        logger.warning(
            f"StrimziSchemaRegistry {name} is missing a listener name, "
            f"using {listener_name}."
        )

    registry_replicas = get_registry_replicas(spec, name)

    return {
        "strimzi_api_version": strimzi_api_version,
        "listener_name": listener_name,
        "service_type": spec.get("serviceType", "ClusterIP"),
        "registry_image": spec.get(
            "registryImage", "confluentinc/cp-schema-registry"
        ),
        "registry_image_tag": spec.get("registryImageTag", "8.0.0"),
        "registry_replicas": registry_replicas,
        "registry_cpu_limit": get_nullable(spec, "cpuLimit"),
        "registry_cpu_request": get_nullable(spec, "cpuRequest"),
        "registry_mem_limit": get_nullable(spec, "memoryLimit"),
        "registry_mem_request": get_nullable(spec, "memoryRequest"),
        "registry_compatibility_level": spec.get(
            "compatibilityLevel", "forward"
        ),
        "security_protocol": spec.get("securityProtocol", "SSL"),
        "registry_topic": spec.get("registryTopic", "registry-schemas"),
        "registry_group_id": spec.get("groupId", "schema-registry"),
    }


def get_registry_replicas(spec: dict[str, Any], name: str) -> int:
    """Get and validate the desired Schema Registry replica count."""
    replicas = spec.get("replicas", 2)
    if replicas < 1:
        raise kopf.PermanentError(
            f"StrimziSchemaRegistry {name} must have at least one replica."
        )
    return replicas


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
    *,
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

    cluster_name = get_cluster_name(body)

    if not cluster_name:
        raise kopf.PermanentError(
            "Missing required label strimzi.io/cluster on "
            "StrimziSchemaRegistry."
        )

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
    if _resource_exists(
        get_deployment,
        name=name,
        namespace=namespace,
        k8s_client=k8s_client,
    ):
        logger.info("Deployment already exists")
    else:
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
            registry_topic=config["registry_topic"],
            registry_group_id=config["registry_group_id"],
        )
        # Set the StrimziSchemaRegistry as the owner
        kopf.adopt(dep_body, owner=cast("kopf.Body", body))
        k8s_apps_v1_api.create_namespaced_deployment(
            body=dep_body, namespace=namespace
        )

    reconcile_pod_disruption_budget(
        replicas=config["registry_replicas"],
        name=name,
        namespace=namespace,
        k8s_client=k8s_client,
        body=body,
        logger=logger,
    )

    # Create the http service to access the Schema Registry REST API
    if _resource_exists(
        get_service,
        name=name,
        namespace=namespace,
        k8s_client=k8s_client,
    ):
        logger.info("Service already exists")
    else:
        svc_body = create_service(
            name=name, service_type=config["service_type"]
        )
        kopf.adopt(svc_body, owner=cast("kopf.Body", body))
        k8s_core_v1_api.create_namespaced_service(
            body=svc_body, namespace=namespace
        )


def reconcile_pod_disruption_budget(
    *,
    replicas: int,
    name: str,
    namespace: str,
    k8s_client: Any,
    body: dict[str, Any],
    logger: Any,
) -> None:
    """Reconcile the PodDisruptionBudget for a Schema Registry.

    A multi-replica registry gets a PodDisruptionBudget that preserves one
    available replica. A single-replica registry does not get a budget because
    that would prevent voluntary eviction of its only pod.
    """
    try:
        get_pod_disruption_budget(
            name=name, namespace=namespace, k8s_client=k8s_client
        )
        pdb_exists = True
    except ApiException as e:
        if e.status == 404:
            pdb_exists = False
        else:
            raise

    policy_api = k8s_client.PolicyV1Api()
    if replicas >= 2:
        if pdb_exists:
            logger.info("PodDisruptionBudget already exists")
            return
        pdb_body = create_pod_disruption_budget(name=name)
        kopf.adopt(pdb_body, owner=cast("kopf.Body", body))
        policy_api.create_namespaced_pod_disruption_budget(
            body=pdb_body, namespace=namespace
        )
    elif pdb_exists:
        try:
            policy_api.delete_namespaced_pod_disruption_budget(
                name=name, namespace=namespace
            )
        except ApiException as e:
            if e.status != 404:
                raise


def _resource_exists(
    getter: Callable[..., Any],
    *,
    name: str,
    namespace: str,
    k8s_client: Any,
) -> bool:
    """Check whether a Kubernetes resource exists."""
    try:
        getter(name=name, namespace=namespace, k8s_client=k8s_client)
    except ApiException as e:
        if e.status == 404:
            return False
        raise
    return True


def register_registry_name(name: str) -> None:
    """Add the name of the registry to the cache."""
    state.registry_names.add(name)
