"""Kopf handlers for the strimzi-registry-operator."""

__all__ = (
    "create_registry",
    "delete_registry",
    "handle_secret_change",
    "start_operator",
)

from strimziregistryoperator.handlers.createregistry import (
    create_registry,
    delete_registry,
)
from strimziregistryoperator.handlers.secretwatcher import handle_secret_change
from strimziregistryoperator.startup import start_operator
