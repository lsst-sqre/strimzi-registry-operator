"""Kopf handlers for the strimzi-registry-operator.
"""

from .secretwatcher import handle_secret_change  # noqa
from .createregistry import create_registry  # noqa
