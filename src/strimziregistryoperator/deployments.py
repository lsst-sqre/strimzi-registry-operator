"""Utilities for creating deployments and related resources."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import kopf

__all__ = (
    "create_deployment",
    "create_service",
    "get_cluster_name",
    "get_kafka_bootstrap_server",
)


def get_kafka_bootstrap_server(
    kafka: dict[str, Any],
    *,
    listener_name: str,
) -> str:
    """Get the bootstrap server address for a Strimzi Kafka cluster
    corresponding to the named listener using information from the
    ``status.listeners`` field.

    Parameters
    ----------
    kafka : dict
        The Kafka resource.
    listener_name : str
        The name of the listener. In Strimzi `v1beta2`, this is
        `spec.listeners[].name`. In Strimzi `v1beta1`, this is
        `spec.listeners.[tls|plain|external]`.

    Returns
    -------
    server : str
        The bootstrap server connection info (``host:port``) for the given
        Kafka listener.
    """
    # Handle the legacy code path in a separate function
    if kafka["apiVersion"] == "kafka.strimzi.io/v1beta1":
        return _get_v1beta1_bootstrap_server(
            kafka, listener_type=listener_name
        )

    # This assumes kafka.strimzi.io/v1beta2 or later

    # As a fallback for some strimzi v1beta2 representations of
    # status.listeners, the status.listeners[].name field might be missing
    # so we need to use the status.listeners[].type field instead. First
    # look up the type corresponding the the named listener.
    listener_types = {
        listener["name"]: listener["type"]
        for listener in kafka["spec"]["kafka"]["listeners"]
    }
    if listener_name not in listener_types:
        raise kopf.TemporaryError(
            f"Listener named {listener_name} is not known. Available "
            f"listeners are {', '.join(listener_types.keys())}"
        )

    try:
        listeners = kafka["status"]["listeners"]
    except KeyError as err:
        raise kopf.TemporaryError(
            "Could not get status.listeners from Kafka resource.",
            delay=10,
        ) from err

    for listener in listeners:
        try:
            # Current v1beta2 strimzi specs include a
            # status.listeners[].name field
            if (
                "name" in listener and listener["name"] == listener_name
            ) or listener["type"] == listener_types[listener_name]:
                return _format_server_address(listener)

        except (KeyError, IndexError):
            continue

    all_names = [listener.get("type") for listener in listeners]
    msg = (
        f"Could not find address of a listener named {listener_name} "
        f"from the Kafka resource. Available names: {', '.join(all_names)}"
    )
    raise kopf.TemporaryError(msg, delay=10)


def _format_server_address(listener_status: dict) -> str:
    # newer versions of Strimzi provide a status.listeners[].bootstrapServers
    # field, but we can compute that from
    # status.listeners[].addresses[0] as a fallback
    if "bootstrapServers" in listener_status:
        return listener_status["bootstrapServers"]
    else:
        address = listener_status["addresses"][0]
        return f"{address['host']}:{address['port']}"


def _get_v1beta1_bootstrap_server(
    kafka: Mapping, *, listener_type: str
) -> str:
    try:
        listeners_status = kafka["status"]["listeners"]
    except KeyError as err:
        raise kopf.TemporaryError(
            "Could not get status.listeners from Kafka resource.",
            delay=10,
        ) from err

    for listener_status in listeners_status:
        try:
            if listener_status["type"] == listener_type:
                # build boostrap server connection info
                return _format_server_address(listener_status)
        except (KeyError, IndexError):
            continue

    all_listener_types = [
        listener.get("type", "UNKNOWN") for listener in listeners_status
    ]
    raise kopf.TemporaryError(
        f"Could not find address of a {listener_type} listener"
        f"from the Kafka resource. Available types: {all_listener_types}",
        delay=10,
    )


def create_deployment(
    *,
    name: str,
    bootstrap_server: str,
    secret_name: str,
    secret_version: str,
    registry_image: str,
    registry_image_tag: str,
    registry_replicas: int,
    registry_cpu_limit: str | None,
    registry_cpu_request: str | None,
    registry_mem_limit: str | None,
    registry_mem_request: str | None,
    compatibility_level: str,
    security_protocol: str,
    registry_topic: str,
) -> dict[str, Any]:
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
    registry_image : `str`
        The Schema Registry docker image.
    registry_image_tag : `str`
        The tag for the Schema Registry docker image.
    registry_replicas : `int`
        The number of replicas for the Schema Registry deployment.
    registry_cpu_limit : `str` or `None`
        Requested CPU limit for the registry container. `None` omits the
        setting from the container spec.
    registry_cpu_request : `str` or `None`
        Requested CPU allocation for the registry container. `None` omits the
        setting from the container spec.
    registry_mem_limit : `str` or `None`
        Requested memory limit for the registry container. `None` omits the
        setting from the container spec.
    registry_mem_request : `str` or `None`
        Requested memory allocation for the registry container. `None` omits
        the setting from the container spec.
    compatiblity_level : `str`
        The default schema compatiblity in a subject. Can be one of:
        none, backward, backward_transitive, forward, forward_transitive,
        full, full_transitive.
    security_protocol : `str`
        The Kafka store security policy. Can be SSL, PLAINTEXT, SASL_PLAINTEXT,
        or SASL_SSL.
    registry_topic : `str`
        The name of the Kafka topic used by the Schema Registry to store
        schemas.

    Returns
    -------
    deployment : `dict`
        The Deployment resource.
    """
    key_prefix = "strimziregistryoperator.roundtable.lsst.codes"

    registry_container = create_container_spec(
        secret_name=secret_name,
        bootstrap_server=bootstrap_server,
        registry_image=registry_image,
        registry_image_tag=registry_image_tag,
        registry_cpu_limit=registry_cpu_limit,
        registry_cpu_request=registry_cpu_request,
        registry_mem_limit=registry_mem_limit,
        registry_mem_request=registry_mem_request,
        compatibility_level=compatibility_level,
        security_protocol=security_protocol,
        registry_topic=registry_topic,
    )

    # The pod template
    template = {
        "metadata": {
            "labels": {"app": name},
            "annotations": {f"{key_prefix}/jksVersion": secret_version},
        },
        "spec": {
            "containers": [registry_container],
            "volumes": [
                {"name": "tls", "secret": {"secretName": secret_name}}
            ],
        },
    }

    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": name,
            "labels": {
                "app": name,
                "app.kubernetes.io/instance": name,
                "app.kubernetes.io/managed-by": "strimzi-registry-operator",
                "app.kubernetes.io/name": "strimzischemaregistry",
                "app.kubernetes.io/part-of": name,
                "app.kubernetes.io/version": registry_image_tag,
            },
        },
        "spec": {
            "replicas": registry_replicas,
            "selector": {"matchLabels": {"app": name}},
            "template": template,
        },
    }


def create_container_spec(
    *,
    secret_name: str,
    bootstrap_server: str,
    registry_image: str,
    registry_image_tag: str,
    registry_cpu_limit: str | None,
    registry_cpu_request: str | None,
    registry_mem_limit: str | None,
    registry_mem_request: str | None,
    compatibility_level: str,
    security_protocol: str,
    registry_topic: str,
) -> dict[str, Any]:
    """Create the container spec for the Schema Registry deployment.

    Parameters
    ----------
    secret_name : `str`
        Name of the Secret resource containing the JKS-formatted keystore
        and truststore.
    secret_version : `str`
        The ``resourceVersion`` of the Secret containing the JKS-formatted
        keystore and truststore.
    registry_image : `str`
        The Schema Registry docker image.
    registry_image_tag : `str`
        The tag for the Schema Registry docker image.
    registry_cpu_limit : `str` or `None`
        Requested CPU limit for the registry container. `None` omits the
        setting from the container spec.
    registry_cpu_request : `str` or `None`
        Requested CPU allocation for the registry container. `None` omits the
        setting from the container spec.
    registry_mem_limit : `str` or `None`
        Requested memory limit for the registry container. `None` omits the
        setting from the container spec.
    registry_mem_request : `str` or `None`
        Requested memory allocation for the registry container. `None` omits
        the setting from the container spec.
    compatiblity_level : `str`
        The default schema compatiblity in a subject. Can be one of:
        none, backward, backward_transitive, forward, forward_transitive,
        full, full_transitive.
    security_protocol : `str`
        The Kafka store security policy. Can be SSL, PLAINTEXT, SASL_PLAINTEXT,
        or SASL_SSL.
    registry_topic : `str`
        The name of the Kafka topic used by the Schema Registry to store
        schemas.
    """
    registry_env = [
        {
            "name": "SCHEMA_REGISTRY_HOST_NAME",
            "valueFrom": {"fieldRef": {"fieldPath": "status.podIP"}},
        },
        {"name": "SCHEMA_REGISTRY_LISTENERS", "value": "http://0.0.0.0:8081"},
        {
            "name": "SCHEMA_REGISTRY_KAFKASTORE_BOOTSTRAP_SERVERS",
            "value": bootstrap_server,
        },
        {
            "name": "SCHEMA_REGISTRY_SCHEMA_COMPATIBILITY_LEVEL",
            "value": compatibility_level,
        },
        {"name": "SCHEMA_REGISTRY_MASTER_ELIGIBILITY", "value": "true"},
        {
            "name": "SCHEMA_REGISTRY_HEAP_OPTS",
            "value": "-Xms512M -Xmx512M",
        },
        {
            "name": "SCHEMA_REGISTRY_KAFKASTORE_TOPIC",
            "value": registry_topic,
        },
        {
            "name": "SCHEMA_REGISTRY_KAFKASTORE_SSL_KEYSTORE_LOCATION",
            "value": "/var/schemaregistry/keystore.jks",
        },
        {
            "name": "SCHEMA_REGISTRY_KAFKASTORE_SSL_KEYSTORE_PASSWORD",
            "valueFrom": {
                "secretKeyRef": {
                    "name": secret_name,
                    "key": "keystore_password",
                }
            },
        },
        {
            "name": "SCHEMA_REGISTRY_KAFKASTORE_SSL_TRUSTSTORE_LOCATION",
            "value": "/var/schemaregistry/truststore.jks",
        },
        {
            "name": "SCHEMA_REGISTRY_KAFKASTORE_SSL_TRUSTSTORE_PASSWORD",
            "valueFrom": {
                "secretKeyRef": {
                    "name": secret_name,
                    "key": "truststore_password",
                }
            },
        },
        {
            "name": "SCHEMA_REGISTRY_KAFKASTORE_SECURITY_PROTOCOL",
            "value": security_protocol,
        },
    ]

    registry_container = {
        "name": "server",
        "image": f"{registry_image}:{registry_image_tag}",
        "imagePullPolicy": "IfNotPresent",
        "ports": [
            {
                "name": "schema-registry",
                "containerPort": 8081,
                "protocol": "TCP",
            }
        ],
        "env": registry_env,
        "volumeMounts": [
            {
                "mountPath": "/var/schemaregistry",
                "name": "tls",
                "readOnly": True,
            }
        ],
        "resources": {},
    }

    if (
        registry_cpu_limit
        or registry_cpu_request
        or registry_mem_limit
        or registry_mem_request
    ):
        resource_spec: dict[str, Any] = {}
        if registry_cpu_limit or registry_mem_limit:
            limit_spec: dict[str, str] = {}
            if registry_cpu_limit:
                limit_spec["cpu"] = registry_cpu_limit
            if registry_mem_limit:
                limit_spec["memory"] = registry_mem_limit
            resource_spec["limits"] = limit_spec
        if registry_cpu_request or registry_mem_request:
            request_spec: dict[str, str] = {}
            if registry_cpu_request:
                request_spec["cpu"] = registry_cpu_request
            if registry_mem_request:
                request_spec["memory"] = registry_mem_request
            resource_spec["requests"] = request_spec
        registry_container["resources"] = resource_spec

    return registry_container


def create_service(
    *, name: str, service_type: str = "ClusterIp"
) -> dict[str, Any]:
    """Create a Service resource for the Schema Registry.

    Parameters
    ----------
    name : `str`
        Name of the StrimziKafkaUser, which is also used as the name of the
        deployment.
    service_type : `str`
        The Kubernetes service type. Typically ClusterIP, but could be
        NodePort for testing with Minikube.

    Returns
    -------
    service : `dict`
        The Service resource.
    """
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": name,
            "labels": {
                "name": name,
                "app.kubernetes.io/instance": name,
                "app.kubernetes.io/managed-by": "strimzi-registry-operator",
                "app.kubernetes.io/name": "strimzischemaregistry",
                "app.kubernetes.io/part-of": name,
            },
        },
        "spec": {
            "type": service_type,
            "ports": [{"name": "schema-registry", "port": 8081}],
            "selector": {
                "app": name,
            },
        },
    }


def update_deployment(
    *,
    deployment: Any,
    secret_version: str,
    k8s_client: Any,
    name: str,
    namespace: str,
) -> None:
    """Update the schema registry deploymeent with a new Secret version
    to trigger a refresh of all its pods.
    """
    key_prefix = "strimziregistryoperator.roundtable.lsst.codes"
    secret_version_key = f"{key_prefix}/jksVersion"
    deployment.metadata.annotations[secret_version_key] = secret_version

    apps_api = k8s_client.AppsV1Api()
    apps_api.patch_namespaced_deployment(
        name=name, namespace=namespace, body=deployment
    )


def get_cluster_name(body: dict) -> str | None:
    """Get the Strimzi cluster name from the metadata labels.

    Parameters
    ----------
    body : dict
        The full body of the StrimziSchemaRegistry resource.

    Returns
    -------
    str | None
        The name of the Strimzi cluster, or None if not found.
    """
    # Extract the cluster name from the metadata labels
    if "metadata" not in body or "labels" not in body["metadata"]:
        return None

    return body.get("metadata", {}).get("labels", {}).get("strimzi.io/cluster")
