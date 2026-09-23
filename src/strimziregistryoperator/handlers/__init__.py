"""Kopf handlers for the strimzi-registry-operator."""

__all__ = (
    "create_registry",
    "delete_registry",
    "handle_secret_change",
    "resume_registry",
    "start_operator",
    "update_registry_group_id",
    "update_registry_pod_disruption_budget",
    "update_registry_replicas",
)

from strimziregistryoperator.handlers.createregistry import (
    create_registry,
    delete_registry,
    resume_registry,
    update_registry_group_id,
    update_registry_pod_disruption_budget,
    update_registry_replicas,
)
from strimziregistryoperator.handlers.secretwatcher import handle_secret_change
from strimziregistryoperator.startup import start_operator
