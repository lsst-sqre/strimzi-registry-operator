"""Tests for the strimziregistryoperator.deployments module.
"""
import kopf
import pytest
import yaml

from strimziregistryoperator.deployments import get_cluster_internal_listener


def test_get_cluster_internal_listener():
    manifest = """
listeners:
- addresses:
  - host: alert-broker-kafka-bootstrap.strimzi.svc
    port: 9092
  bootstrapServers: alert-broker-kafka-bootstrap.strimzi.svc:9092
  type: internal
- addresses:
  - host: 10.106.209.159
    port: 9094
  bootstrapServers: 10.106.209.159:9094
  type: external
observedGeneration: 1
    """
    kafka = yaml.safe_load(manifest)

    listener = get_cluster_internal_listener(kafka)
    assert listener == "alert-broker-kafka-bootstrap.strimzi.svc:9092"


def test_get_cluster_internal_listener_when_none_exists():
    manifest = """
listeners:
- addresses:
  - host: 10.106.209.159
    port: 9094
  bootstrapServers: 10.106.209.159:9094
  type: external
observedGeneration: 1
    """
    kafka = yaml.safe_load(manifest)

    with pytest.raises(kopf.PermanentError):
        get_cluster_internal_listener(kafka)
