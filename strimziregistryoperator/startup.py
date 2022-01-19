"""Code intended to run on start-up, before running any handlers.
"""

__all__ = ("start_operator",)

from kubernetes.client.rest import ApiException

from . import state
from .k8s import create_k8sclient


def start_operator():
    """Start up the operator, priming its cache of the application state."""
    api = create_k8sclient().CustomObjectsApi()

    try:
        response = api.list_namespaced_custom_object(
            "roundtable.lsst.codes",
            "v1beta1",
            state.namespace,
            "strimzischemaregistries",
            timeout_seconds=60,
        )
    except ApiException as e:
        print(
            "Exception when calling CustomObjectsApi->"
            "list_namespaced_custom_object: %s\n" % e
        )
        return

    # Add these StrimziSchemaRegistry names to state.registry_names
    for ssr in response["items"]:
        name = ssr["metadata"]["name"]
        state.registry_names.add(name)
