"""Tests for the strimziregistryoperator.deployments module."""

import kopf
import pytest
import yaml

from strimziregistryoperator.deployments import (
    create_service,
    get_kafka_bootstrap_server,
)


def test_get_cluster_listener_strimzi_v1beta1():
    manifest = """
apiVersion: kafka.strimzi.io/v1beta1
kind: Kafka
metadata:
  name: events
spec:
  kafka:
    listeners:
      tls:
        authentication:
          type: "tls"
status:
  listeners:
  - addresses:
    - host: events-kafka-bootstrap.events.svc
      port: 9093
    type: tls
"""
    kafka = yaml.safe_load(manifest)

    # Get bootstrap server
    listener = get_kafka_bootstrap_server(kafka, listener_name="tls")
    assert listener == "events-kafka-bootstrap.events.svc:9093"


def test_get_cluster_listener_bootstrap_v1beta2_oldstyle():
    manifest = r"""
apiVersion: kafka.strimzi.io/v1beta2
kind: Kafka
metadata:
  name: alert-broker
spec:
  kafka:
    listeners:
      - name: plain
        port: 9092
        type: internal
        tls: false
      - name: tls
        port: 9093
        type: internal
        tls: true
        authentication:
          type: tls
      - name: external
        port: 9094
        type: route
        tls: true
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
    type: route
"""
    kafka = yaml.safe_load(manifest)

    listener = get_kafka_bootstrap_server(kafka, listener_name="plain")
    assert listener == "alert-broker-kafka-bootstrap.strimzi.svc:9092"

    listener = get_kafka_bootstrap_server(kafka, listener_name="external")
    assert listener == "10.106.209.159:9094"

    with pytest.raises(kopf.TemporaryError):
        get_kafka_bootstrap_server(kafka, listener_name="missing")


def test_get_cluster_listener_bootstrap_v1beta2_newstyle():
    manifest = r"""
apiVersion: kafka.strimzi.io/v1beta2
kind: Kafka
metadata:
  name: my-cluster
spec:
  kafka:
    listeners:
      - name: plain
        port: 9092
        type: internal
        tls: false
      - name: tls
        port: 9093
        type: internal
        tls: true
        authentication:
          type: tls
      - name: external1
        port: 9094
        type: route
        tls: true
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


def test_create_clusterip_service() -> None:
    """Create a ClusterIP service resource spec for the Schema Registry."""
    resource = create_service(
        name="confluent-schema-registry", service_type="ClusterIP"
    )
    assert resource["spec"]["type"] == "ClusterIP"


def test_create_nodeport_service() -> None:
    """Create a NodePort service resource spec for the Schema Registry."""
    resource = create_service(
        name="confluent-schema-registry", service_type="NodePort"
    )
    assert resource["spec"]["type"] == "NodePort"
