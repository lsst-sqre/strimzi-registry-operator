"""Kopf handlers for the strimzi-registry-operator."""

__all__ = (
    "create_registry",
    "handle_secret_change",
)

from strimziregistryoperator.handlers.createregistry import create_registry
from strimziregistryoperator.handlers.secretwatcher import handle_secret_change
from strimziregistryoperator.startup import start_operator

start_operator(logger=None)
