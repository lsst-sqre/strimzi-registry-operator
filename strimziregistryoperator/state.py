"""Constructed (cached) state as module-level attributes.
"""

cluster_name = 'events'
"""The name of the Kafka cluster serviced by the operator.

TODO: make this configurable.
"""

namespace = 'events'
"""The name of the Kubernetes namespace monitored by this operator.

TODO: make this configurable.
"""


registry_names = set()
"""Cache of StrimziSchemaRegistry names being tracked.

This state is updated as StrimziSchemaRegistry resources are detected and
monitored.
"""
