"""Kopf handler to react to changes to Strimzi-generated Kubernetes secrets
for the cluster CA certificate or the client certificates.
"""

__all__ = (
    "handle_secret_change",
    "refresh_with_new_client_secret",
    "refresh_with_new_cluster_ca",
)

from typing import Any, cast

import kopf
from kubernetes.client.exceptions import ApiException

from .. import state
from ..certprocessor import create_secret
from ..deployments import get_cluster_name, update_deployment
from ..k8s import create_k8sclient, get_deployment, get_secret, get_ssr


@kopf.on.event("", "v1", "secrets")  # type: ignore[arg-type]
def handle_secret_change(
    *,
    spec: dict[str, Any],
    meta: dict[str, Any],
    namespace: str,
    name: str,
    uid: str,
    event: dict[str, Any],
    body: dict[str, Any],
    logger: Any,
    **kwargs: Any,
) -> None:
    """Handle changes in secrets managed by Strimzi for the
    KafkaUser corresponding to a StrimziSchemaRegistry deployment.

    Parameters
    ----------
    spec : `dict`
        The specification of the Secret.
    meta : `dict`
        The metadata of the Secret, including labels.
    namespace : `str`
        The Kubernetes namespace where the Secret is located.
    name : `str`
        The name of the Secret.
    uid : `str`
        The unique identifier of the Secret.
    event : `dict`
        The event type, such as "ADDED", "MODIFIED", or "DELETED".
    body : `dict`
        The body of the Secret, containing the data.
    logger : `Any`
        A logger instance for logging messages.
    kwargs : `Any`
        Additional keyword arguments, if any.
    """
    # Act only on Secrets that have been created or updated
    if event["type"] not in ("ADDED", "MODIFIED"):
        return

    # Act only on Secrets with the matching strimzi.io/cluster configuration.
    try:
        if meta["labels"]["strimzi.io/cluster"] != state.cluster_name:
            return
    except KeyError:
        # didn't have a strimzio.io/cluster key; so no action is needed.
        return

    if name == f"{state.cluster_name}-cluster-ca-cert":
        # Handle a change in the cluster CA certificate
        refresh_with_new_cluster_ca(
            cluster_ca_secret=body, namespace=namespace, logger=logger
        )
    elif name in state.registry_names:
        # Handle a change in the KafkaUser client certificate of a
        # StrimziSchemaRegistry
        refresh_with_new_client_secret(
            kafkauser_secret=body, namespace=namespace, logger=logger
        )


def refresh_with_new_cluster_ca(
    *,
    cluster_ca_secret: dict[str, Any],
    namespace: str,
    logger: Any,
) -> None:
    """Refresh the StrimziSchemaRegistry deployments with a new cluster
    CA certificate.

    Parameters
    ----------
    cluster_ca_secret : `dict`
        The Kubernetes Secret containing the new cluster CA certificate.
    namespace : `str`
        The Kubernetes namespace where the StrimziSchemaRegistry deployments
        are located.
    logger : `Any`
        A logger instance for logging messages.
    """
    k8s_client = create_k8sclient()

    cluster = cluster_ca_secret["metadata"]["labels"]["strimzi.io/cluster"]

    # Iterate over a snapshot so stale cache entries can be removed safely.
    for registry_name in tuple(state.registry_names):
        ssr_body = _get_tracked_registry(
            name=registry_name,
            namespace=namespace,
            k8s_client=k8s_client,
            logger=logger,
        )
        if ssr_body is None:
            continue

        secret = create_secret(
            kafka_username=registry_name,
            namespace=namespace,
            cluster=cluster,
            owner=cast("kopf.Body", ssr_body),
            k8s_client=k8s_client,
            cluster_ca_secret=cluster_ca_secret,
            logger=logger,
        )

        secret_name = secret["metadata"]["name"]

        # Get the secret so now it has the resourceVersion metadata
        secret_version = get_secret(
            name=secret_name,
            namespace=namespace,
            k8s_client=k8s_client,
        )["metadata"]["resourceVersion"]

        deployment = get_deployment(
            name=registry_name,
            namespace=namespace,
            k8s_client=k8s_client,
            raw=False,
        )

        update_deployment(
            deployment=deployment,
            secret_version=secret_version,
            name=registry_name,
            namespace=namespace,
            k8s_client=k8s_client,
        )


def refresh_with_new_client_secret(
    *,
    kafkauser_secret: dict[str, Any],
    namespace: str,
    logger: Any,
) -> None:
    """Refresh the StrimziSchemaRegistry deployments with a new client secret.

    Parameters
    ----------
    kafkauser_secret : `dict`
        The Kubernetes Secret containing the new client secret for the
        KafkaUser.
    namespace : `str`
        The Kubernetes namespace where the StrimziSchemaRegistry deployments
        are located.
    logger : `Any`
        A logger instance for logging messages.
    """
    # Create a Kubernetes client to interact with the cluster
    k8s_client = create_k8sclient()

    # Extract the Kafka username and cluster from the secret metadata
    kafka_username = kafkauser_secret["metadata"]["name"]
    cluster = kafkauser_secret["metadata"]["labels"]["strimzi.io/cluster"]

    # Get the StrimziSchemaRegistry resource for this KafkaUser.
    ssr_body = _get_tracked_registry(
        name=kafka_username,
        namespace=namespace,
        k8s_client=k8s_client,
        logger=logger,
    )
    if ssr_body is None:
        return

    # Create or update the Secret with the new client secret
    secret = create_secret(
        kafka_username=kafka_username,
        namespace=namespace,
        cluster=cluster,
        owner=cast("kopf.Body", ssr_body),
        k8s_client=k8s_client,
        client_secret=kafkauser_secret,
        logger=logger,
    )

    secret_name = secret["metadata"]["name"]

    # Get the secret so now it has the resourceVersion metadata
    secret_version = get_secret(
        name=secret_name,
        namespace=namespace,
        k8s_client=k8s_client,
    )["metadata"]["resourceVersion"]

    # Get the Deployment for this KafkaUser
    deployment = get_deployment(
        name=kafka_username,
        namespace=namespace,
        k8s_client=k8s_client,
        raw=False,
    )

    # Update the Deployment with the new Secret version
    update_deployment(
        deployment=deployment,
        secret_version=secret_version,
        name=kafka_username,
        namespace=namespace,
        k8s_client=k8s_client,
    )


def _get_tracked_registry(
    *,
    name: str,
    namespace: str,
    k8s_client: Any,
    logger: Any,
) -> dict[str, Any] | None:
    """Get a registry if it still exists and belongs to this operator."""
    try:
        registry = get_ssr(
            name=name, namespace=namespace, k8s_client=k8s_client
        )
    except ApiException as e:
        if e.status != 404:
            raise
        logger.info(f"StrimziSchemaRegistry {name} no longer exists.")
        state.registry_names.discard(name)
        return None

    if get_cluster_name(registry) != state.cluster_name:
        logger.info(
            f"StrimziSchemaRegistry {name} no longer belongs to Kafka "
            f"cluster {state.cluster_name}."
        )
        state.registry_names.discard(name)
        return None

    return registry
