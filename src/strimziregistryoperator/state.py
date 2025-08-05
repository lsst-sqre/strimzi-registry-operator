"""Constructed (cached) state as module-level attributes."""

import os

cluster_name = os.environ.get("SSR_CLUSTER_NAME", "events")
"""The name of the Kafka cluster serviced by the operator. """

namespace = os.environ.get("SSR_NAMESPACE", "events")
"""The name of the Kubernetes namespace monitored by this operator. """


registry_names: set[str] = set()
"""Cache of StrimziSchemaRegistry names being tracked.

This state is updated as StrimziSchemaRegistry resources are detected and
monitored.
"""
