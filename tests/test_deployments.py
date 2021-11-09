"""Tests for the strimziregistryoperator.deployments module.
"""

import kopf
import pytest
import yaml

from strimziregistryoperator.deployments import get_cluster_listener


def test_get_cluster_listener():
    manifest = (
        'status:\n'
        '  conditions:\n'
        '  - lastTransitionTime: 2019-10-15T21:27:36+0000\n'
        '    status: "True"\n'
        '    type: Ready\n'
        '  listeners:\n'
        '  - addresses:\n'
        '    - host: events-kafka-bootstrap.events.svc\n'
        '      port: 9093\n'
        '    type: tls\n'
        '  observedGeneration: 1\n'
    )
    kafka = yaml.safe_load(manifest)

    # Get listener without name - should default to 'tls'
    listener = get_cluster_listener(kafka)
    assert listener == 'events-kafka-bootstrap.events.svc:9093'

    listener = get_cluster_listener(kafka, "tls")
    assert listener == 'events-kafka-bootstrap.events.svc:9093'


def test_get_cluster_listener_bootstrap():
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

    listener = get_cluster_listener(kafka, "internal")
    assert listener == 'alert-broker-kafka-bootstrap.strimzi.svc:9092'

    listener = get_cluster_listener(kafka, "external")
    assert listener == '10.106.209.159:9094'

    with pytest.raises(kopf.TemporaryError):
        get_cluster_listener(kafka, "missing")
