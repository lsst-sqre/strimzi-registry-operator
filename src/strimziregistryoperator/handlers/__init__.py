"""Kopf handlers for the strimzi-registry-operator."""

from ..startup import start_operator

start_operator()

from .createregistry import create_registry  # noqa
from .secretwatcher import handle_secret_change  # noqa
