"""Tests for the strimziregistryoperator.deployments module.
"""

import yaml

from strimziregistryoperator.deployments import (
    get_cluster_tls_listener)


def test_get_cluster_tls_listener():
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

    listener = get_cluster_tls_listener(kafka)
    assert listener == 'events-kafka-bootstrap.events.svc:9093'
