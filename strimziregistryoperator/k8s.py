__all__ = ('create_k8sclient', 'get_deployment', 'get_service', 'get_service_ports', 'get_secret')

import json

import kubernetes


def create_k8sclient():
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


def get_deployment(*, name, namespace, k8s_client, raw=True):
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
    if raw:
        preload_content = False
    else:
        preload_content = True

    api = k8s_client.AppsV1Api()
    result = api.read_namespaced_deployment(
        name=name,
        namespace=namespace,
        _preload_content=preload_content)
    if raw:
        return json.loads(result.data)
    else:
        return result


def get_service_ports(*, name, namespace, k8s_client):
    """Get the ports associated with a Service resource.

    Parameters
    ----------
    namespace : `str`
        The Kubernetes namespace where the Strimzi Kafka cluster operates.
    name : `str`
        The name of the Service.
    k8s_client
        A Kubernetes client (see `create_k8sclient`).

    Returns
    -------
    ports
        A dict of port names to their specs.
    """
    service = get_service(name, namespace, k8s_client)
    ports = {}
    for p in service["spec"]["ports"]:
        ports[p["name"]] = p
    return ports


def get_service(*, name, namespace, k8s_client, raw=True):
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
    if raw:
        preload_content = False
    else:
        preload_content = True

    api = k8s_client.CoreV1Api()
    result = api.read_namespaced_service(
        name=name,
        namespace=namespace,
        _preload_content=preload_content)
    if raw:
        return json.loads(result.data)
    else:
        return result


def get_secret(*, namespace, name, k8s_client, raw=True):
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
    if raw:
        preload_content = False
    else:
        preload_content = True

    api = k8s_client.CoreV1Api()
    result = api.read_namespaced_secret(
        name=name,
        namespace=namespace,
        _preload_content=preload_content)
    if raw:
        return json.loads(result.data)
    else:
        return result


def get_ssr(*, namespace, name, k8s_client, raw=True):
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
    if raw:
        preload_content = False
    else:
        preload_content = True

    api = k8s_client.CustomObjectsApi()
    result = api.get_namespaced_custom_object(
        group='roundtable.lsst.codes',
        version='v1beta1',
        namespace=namespace,
        plural='ssrs',
        name=name,
        _preload_content=preload_content)
    if raw:
        return json.loads(result.data)
    else:
        return result
