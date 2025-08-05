"""Tests for the strimziregistryoperator.deployments module."""

from __future__ import annotations

import kopf
import pytest
import yaml

from strimziregistryoperator.deployments import (
    create_deployment,
    create_service,
    get_kafka_bootstrap_server,
)


def test_get_cluster_listener_strimzi_v1beta1() -> None:
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


def test_get_cluster_listener_bootstrap_v1beta2_oldstyle() -> None:
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


def test_get_cluster_listener_bootstrap_v1beta2_newstyle() -> None:
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


def get_env_value(env: list[dict[str, str]], name: str) -> str | None:
    """Get the value of an environment variable in the container spec.env."""
    for item in env:
        if item["name"] == name:
            return item["value"]
    return None


def test_create_deployment_configurations() -> None:
    """Create a schema registry deployment body with configurations."""
    registry_image = "demo/testimage"
    registry_image_tag = "1.2.3"

    dep_body = create_deployment(
        name="example-server",
        bootstrap_server="example-server.default.svc:9093",
        secret_name="example-server",
        secret_version="1",
        registry_image=registry_image,
        registry_image_tag=registry_image_tag,
        registry_cpu_limit=None,
        registry_mem_limit=None,
        registry_cpu_request=None,
        registry_mem_request=None,
        compatibility_level="backward",
        security_protocol="SSL",
    )
    assert dep_body["spec"]["template"]["spec"]["containers"][0]["image"] == (
        f"{registry_image}:{registry_image_tag}"
    )

    env = dep_body["spec"]["template"]["spec"]["containers"][0]["env"]
    assert (
        get_env_value(env, "SCHEMA_REGISTRY_SCHEMA_COMPATIBILITY_LEVEL")
        == "backward"
    )
    assert (
        get_env_value(env, "SCHEMA_REGISTRY_KAFKASTORE_SECURITY_PROTOCOL")
        == "SSL"
    )

    # no resource settings
    assert (
        "resources"
        not in dep_body["spec"]["template"]["spec"]["containers"][0]
    )


def test_create_deployment_resource_settings() -> None:
    """Create a schema registry deployment body with a customized image."""
    registry_image = "demo/testimage"
    registry_image_tag = "1.2.3"

    dep_body = create_deployment(
        name="example-server",
        bootstrap_server="example-server.default.svc:9093",
        secret_name="example-server",
        secret_version="1",
        registry_image=registry_image,
        registry_image_tag=registry_image_tag,
        registry_cpu_limit="1000m",
        registry_mem_limit="1000M",
        registry_cpu_request="100m",
        registry_mem_request="768M",
        compatibility_level="forward",
        security_protocol="SSL",
    )
    resources = dep_body["spec"]["template"]["spec"]["containers"][0][
        "resources"
    ]
    assert resources["limits"]["cpu"] == "1000m"
    assert resources["limits"]["memory"] == "1000M"
    assert resources["requests"]["cpu"] == "100m"
    assert resources["requests"]["memory"] == "768M"
