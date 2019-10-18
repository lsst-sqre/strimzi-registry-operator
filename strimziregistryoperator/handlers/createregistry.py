"""Kopf handler for the creation of a StrimziSchemaRegistry.
"""

import kopf


@kopf.on.create('roundtable.lsst.codes', 'v1beta1', 'strimzischemaregistries')
def create_registry(spec, meta, namespace, name, uid, logger, **kwargs):
    # 1. Create the secrets
    # 2. Create the deployment
    # 3. Create the service
    logger.info(f'Creating a new registry deployment: "{name}"')
