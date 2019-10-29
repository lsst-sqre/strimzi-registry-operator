__all__ = ('create_k8sclient', 'get_deployment', 'get_service')

import json

import kubernetes


def create_k8sclient():
    try:
        kubernetes.config.load_incluster_config()
    except Exception:
        kubernetes.config.load_kube_config()
    kubernetes.client.configuration.assert_hostname = False
    return kubernetes.client


def get_deployment(*, name, namespace, k8s_client, raw=True):
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


def get_service(*, name, namespace, k8s_client, raw=True):
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
