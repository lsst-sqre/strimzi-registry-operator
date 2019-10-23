"""Constructed (cached) state as module-level attributes.
"""

cluster_name = 'events'
"""The name of the Kafka cluster serviced by the operator.

TODO: make this configurable.
"""


registry_names = set()
"""Cache of StrimziSchemaRegistry names being tracked.

This state is updated as StrimziSchemaRegistry resources are detected and
monitored.
"""
