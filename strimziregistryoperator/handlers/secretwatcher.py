"""Kopf handler to react to changes to Strimzi-generated Kubernetes secrets
for the cluster CA certificate or the client certificates.
"""

import kopf


@kopf.on.event('', 'v1', 'secrets')
def handle_secret_change(spec, meta, namespace, name, uid, event, body, logger,
                         **kwargs):
    logger.info(f'Detected secret change: "{name}" ({event})')
