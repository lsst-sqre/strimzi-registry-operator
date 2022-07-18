"""Tests for the strimziregistryoperator.deployments module."""

import kopf
import pytest
import yaml

from strimziregistryoperator.deployments import get_kafka_bootstrap_server


def test_get_cluster_listener_strimzi_v1beta1():
    manifest = (
        "status:\n"
        "  listeners:\n"
        "  - addresses:\n"
        "    - host: events-kafka-bootstrap.events.svc\n"
        "      port: 9093\n"
        "    type: tls\n"
        "  observedGeneration: 1\n"
    )
    kafka = yaml.safe_load(manifest)

    # Get bootstrap server
    listener = get_kafka_bootstrap_server(kafka, listener_name="tls")
    assert listener == "events-kafka-bootstrap.events.svc:9093"


def test_get_cluster_listener_bootstrap_v1beta2_oldstyle():
    manifest = r"""
status:
  clusterId: Ob95JyXzTlecnvjKVx3E2A
  conditions:
  - lastTransitionTime: "2021-10-29T18:57:10.607Z"
    status: "True"
    type: Ready
  listeners:
  - addresses:
    - host: alert-broker-kafka-bootstrap.strimzi.svc
      port: 9092
    bootstrapServers: alert-broker-kafka-bootstrap.strimzi.svc:9092
    certificates:
    - |
      -----BEGIN CERTIFICATE-----
      redacted
      -----END CERTIFICATE-----
    type: internal
  - addresses:
    - host: 10.106.209.159
      port: 9094
    bootstrapServers: 10.106.209.159:9094
    certificates:
    - |
      -----BEGIN CERTIFICATE-----
      redacted
      -----END CERTIFICATE-----
    type: external
  observedGeneration: 1
"""
    kafka = yaml.safe_load(manifest)

    listener = get_kafka_bootstrap_server(kafka, listener_name="internal")
    assert listener == "alert-broker-kafka-bootstrap.strimzi.svc:9092"

    listener = get_kafka_bootstrap_server(kafka, listener_name="external")
    assert listener == "10.106.209.159:9094"

    with pytest.raises(kopf.TemporaryError):
        get_kafka_bootstrap_server(kafka, listener_name="missing")


def test_get_cluster_listener_bootstrap_v1beta2_newstyle():
    manifest = r"""
status:
  listeners:
    - addresses:
        - host: sasquatch-kafka-bootstrap.sasquatch.svc
          port: 9092
      bootstrapServers: 'sasquatch-kafka-bootstrap.sasquatch.svc:9092'
      name: plain
      type: plain
    - addresses:
        - host: sasquatch-kafka-bootstrap.sasquatch.svc
          port: 9093
      bootstrapServers: 'sasquatch-kafka-bootstrap.sasquatch.svc:9093'
      certificates:
        - |
          -----BEGIN CERTIFICATE-----
          redacted
          -----END CERTIFICATE-----
      name: tls
      type: tls
"""
    kafka = yaml.safe_load(manifest)

    server = get_kafka_bootstrap_server(kafka, listener_name="plain")
    assert server == "sasquatch-kafka-bootstrap.sasquatch.svc:9092"

    server = get_kafka_bootstrap_server(kafka, listener_name="tls")
    assert server == "sasquatch-kafka-bootstrap.sasquatch.svc:9093"
