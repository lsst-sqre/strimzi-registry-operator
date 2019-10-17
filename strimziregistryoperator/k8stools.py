__all__ = ('create_k8sclient',)

import kubernetes


def create_k8sclient(incluster=True):
    if incluster:
        kubernetes.config.load_incluster_config()
    else:
        kubernetes.config.load_kube_config()
    kubernetes.client.configuration.assert_hostname = False
    return kubernetes.client
