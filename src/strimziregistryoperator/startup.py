"""Code intended to run on start-up, before running any handlers."""

__all__ = ("start_operator",)

from typing import Any

import kopf
import structlog
from kubernetes.client.rest import ApiException

from strimziregistryoperator import state
from strimziregistryoperator.deployments import get_cluster_name
from strimziregistryoperator.k8s import create_k8sclient


@kopf.on.startup()
def start_operator(logger: Any, **kwargs: Any) -> None:
    """Start up the operator, priming its cache of the application state."""
    if logger is None:
        logger = structlog.getLogger(__name__)

    api = create_k8sclient().CustomObjectsApi()

    try:
        response = api.list_namespaced_custom_object(
            "roundtable.lsst.codes",
            "v1beta1",
            state.namespace,
            "strimzischemaregistries",
            timeout_seconds=60,
        )
    except ApiException:
        logger.exception(
            "Exception when calling CustomObjectsApi->"
            "list_namespaced_custom_object\n"
        )
        return

    registry_names = {
        ssr["metadata"]["name"]
        for ssr in response["items"]
        if get_cluster_name(ssr) == state.cluster_name
    }
    state.registry_names.clear()
    state.registry_names.update(registry_names)
