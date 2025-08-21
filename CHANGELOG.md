# Change log

## 0.7.0 (2025-08-21)

This release adds significant improvements to the Strimzi Registry Operator:

- Modernize the operator codebase, adopt uv-based Python workflow with `pyproject.toml`, refresh dependencies, update GitHub Actions, and improve typing/formatting.
- Update minikube workflow; test fixtures and docs refreshed.
- Update RBAC for newer Kopf behavior and grant cluster-wide list of namespaces and watch CRDs.
- Support for configuring Schema Registry **topic name** and the number of deployment **replicas** via `StrimziSchemaRegistry` CR.
- Proper handling of `spec.compatibilityLevel` setting.
- The Kafka cluster name is now read from the `strimzi.io/cluster` label on the `StrimziSchemaRegistry` CR.
  **Breaking change:** this label is now required.
- Default Schema Registry image tag updated to 8.0.0.
- Deprecated `strimzi-version` field replaced with `strimziVersion`.
- Operator now correctly **recreates the JKS secret** when Kafka CA or client certs rotate.
- Expanded documentation covering access the **Schema Registry API** after deployment, new configuration options and improved the **installation instructions**.

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
