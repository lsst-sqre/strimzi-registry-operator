"""Helpers for interacting with Kubernetes APIs."""

__all__ = ("create_k8sclient", "get_deployment", "get_secret", "get_service")

import json
from typing import Any

import kubernetes


def create_k8sclient() -> kubernetes.client:
    """Get a Kubernetes client configured with available cluster
    authentication.

    If in-cluster authentication is available, that is used. Otherwise
    this function falls-back to using a kubectl config file, which is
    appropriate for development.
    """
    try:
        kubernetes.config.load_incluster_config()
    except Exception:
        kubernetes.config.load_kube_config()
    kubernetes.client.configuration.assert_hostname = False
    return kubernetes.client


def get_deployment(
    *,
    name: str,
    namespace: str,
    k8s_client: Any,
    raw: bool = True,
) -> dict[str, Any] | Any:
    """Get a Deployment resource.

    Parameters
    ----------
    namespace : `str`
        The Kubernetes namespace where the Strimzi Kafka cluster operates.
    name : `str`
        The name of the Deployment.
    k8s_client
        A Kubernetes client (see `create_k8sclient`).
    raw : `bool`
        If `True`, the raw Kubernetes manifest is returned as a `dict`.
        Otherwise the Python object representation of the resource is returned.

    Returns
    -------
    service
        The Kubernetes Deployment resource either as a `dict` or an object.
    """
    preload_content = not raw

    api = k8s_client.AppsV1Api()
    result = api.read_namespaced_deployment(
        name=name, namespace=namespace, _preload_content=preload_content
    )
    if raw:
        return json.loads(result.data)
    else:
        return result


def get_service(
    *,
    namespace: str,
    name: str,
    k8s_client: Any,
    raw: bool = True,
) -> dict[str, Any] | Any:
    """Get a Service resource.

    Parameters
    ----------
    namespace : `str`
        The Kubernetes namespace where the Strimzi Kafka cluster operates.
    name : `str`
        The name of the Service.
    k8s_client
        A Kubernetes client (see `create_k8sclient`).
    raw : `bool`
        If `True`, the raw Kubernetes manifest is returned as a `dict`.
        Otherwise the Python object representation of the resource is returned.

    Returns
    -------
    service
        The Kubernetes Service resource either as a `dict` or an object.
    """
    preload_content = not raw

    api = k8s_client.CoreV1Api()
    result = api.read_namespaced_service(
        name=name, namespace=namespace, _preload_content=preload_content
    )
    if raw:
        return json.loads(result.data)
    else:
        return result


def get_secret(
    *,
    namespace: str,
    name: str,
    k8s_client: Any,
    raw: bool = True,
) -> dict[str, Any] | Any:
    """Get a Secret resource.

    Parameters
    ----------
    namespace : `str`
        The Kubernetes namespace where the Strimzi Kafka cluster operates.
    name : `str`
        The name of the Secret.
    k8s_client
        A Kubernetes client (see `create_k8sclient`).
    raw : `bool`
        If `True`, the raw Kubernetes manifest is returned as a `dict`.
        Otherwise the Python object representation of the resource is returned.

    Returns
    -------
    secret
        The Kubernetes Secret resource either as a `dict` or an object.
    """
    preload_content = not raw

    api = k8s_client.CoreV1Api()
    result = api.read_namespaced_secret(
        name=name, namespace=namespace, _preload_content=preload_content
    )
    if raw:
        return json.loads(result.data)
    else:
        return result


def get_ssr(
    *,
    namespace: str,
    name: str,
    k8s_client: Any,
    raw: bool = True,
) -> dict[str, Any] | Any:
    """Get a StrimziSchemaRegistry resource.

    Parameters
    ----------
    namespace : `str`
        The Kubernetes namespace where the Strimzi Kafka cluster operates.
    name : `str`
        The name of the StrimziSchemaRegistry.
    k8s_client
        A Kubernetes client (see `create_k8sclient`).
    raw : `bool`
        If `True`, the raw Kubernetes manifest is returned as a `dict`.
        Otherwise the Python object representation of the resource is returned.

    Returns
    -------
    ssr
        The Kubernetes StrimziSchemaRegistry resource either as a `dict` or an
        object.
    """
    preload_content = not raw

    api = k8s_client.CustomObjectsApi()
    result = api.get_namespaced_custom_object(
        group="roundtable.lsst.codes",
        version="v1beta1",
        namespace=namespace,
        plural="ssrs",
        name=name,
        _preload_content=preload_content,
    )
    if raw:
        return json.loads(result.data)
    else:
        return result
