# Change log

## 0.6.0 (2022-08-03)

Strimzi Registry Operator now adds the [recommended Kubernetes labels](https://kubernetes.io/docs/concepts/overview/working-with-objects/common-labels/#labels) to the `Deployment` and `Service` resources for the Confluent Schema Registry deployment.

## 0.5.0 (2022-07-28)

This release adds significant improvements for compatibility with newer versions of Strimzi and the Confluent Schema Registry.
The `StrimziSchemaRegistry` CRD has new and revised fields, which you should review before deploying this version:

- The `spec.listener` field in `StrimziSchemaRegistry` now refers to the **name** of the of the listener — the `spec.kafka.listeners[].name` field of Strimzi's `Kafka` resource (with the `kafka.strimzi.io/v1beta2` Strimzi API).
  With older versions of strimzi (API version `kafka.strimzi.io/v1beta1`), this refers to the type, which also doubled as a name in the `spec.kafka.listeners.type` or `.external` or `.plain`.
- The Schema Registry's security protocol ([kafkastore.security.protocol](https://docs.confluent.io/platform/current/schema-registry/installation/config.html#kafkastore-security-protocol)) is now configurable through the `spec.securityProtocol` of the `StrimziSchemaRegistry` resource. Default is `SSL`, but can be changed for plain text or SASL users.
- The default subject compatibility level in the Schema Registry ([schema.compatibility.level](https://docs.confluent.io/platform/current/schema-registry/installation/config.html#schema-compatibility-level)) can be set with the `spec.compatibilityLevel` field of `StrimziSchemaRegistry. Details, as from previous versions of Strimzi Registry Operator, is `forward`.
- The Schema Registry Docker image is now configurable via `registryImage` and `registryImageTag` fields of `StrimziSchemaRegistry`. The defaults are updated to Schema Registry 7.2.1.
- You can now set CPU and memeory requests and limits for the Schema Registry through the `StrimziSchemaRegistry`.

The default container registry for Strimzi Registry Operator is now `ghcr.io` (GitHub Container Registry): `ghcr.io/lsst-sqre/strimzi-registry-operator`.
