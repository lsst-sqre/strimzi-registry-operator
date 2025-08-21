# strimzi-registry-operator

A Kubernetes Operator for running the [Confluent Schema Registry](https://docs.confluent.io/current/schema-registry/index.html) in a [Strimzi](https://strimzi.io)-based [Kafka](https://kafka.apache.org/) cluster that's optionally secured with TLS.

Overview:

- Once you deploy a `StrimziSchemaRegistry` resource, the operator creates a Kubernetes deployment of the Confluent Schema Registry, along with an associated Kubernetes service and secret.
- Works with Strimzi's TLS authentication and authorization by converting the TLS certificate associated with a KafkaUser into a JKS-formatted keystore and truststore that's used by Confluence Schema Registry.
- When Strimzi updates either the Kafka cluster's CA certificate or the KafkaUser's client certificates, the operator automatically recreates the JKS truststore/keystore secrets and triggers a rolling restart of the Schema Registry pods.

## Deploy the operator

There are two steps for running strimzi-registry-operator.
First, you'll need to deploy the operator itself — this is described in this section.
Once the operator is deployed, you can deploy `StrimziSchemaRegistry` resources that actually create and maintain a Confluent Schema Registry application (this is discussed in later sections).

Two operator deployment options are available: [Helm](https://helm.sh) and [Kustomize](https://kustomize.io).

### With Helm

A Helm chart is available for strimzi-registry-operator on GitHub at [lsst-sqre/charts](https://github.com/lsst-sqre/charts/tree/master/charts/strimzi-registry-operator):

```sh
helm repo add lsstsqre https://lsst-sqre.github.io/charts/
helm repo update
helm install strimzi-registry-operator lsstsqre/strimzi-registry-operator \
  --create-namespace \
  --namespace strimzi-registry-operator \
  --set clusterName=events \
  --set clusterNamespace=events \
```

In this example, the operator is deployed in the `strimzi-registry-operator` namespace.

The following values are configured:

- `clusterName`: Name of the Strimzi Kafka cluster the registry connects to.
- `clusterNamespace`: Namespace where the Strimzi Kafka cluster is deployed.
  The operator watches this namespace for the `StrimziSchemaRegistry`, `KafkaUser` and `KafkaTopic` resources.

[See the Helm chart's README](https://github.com/lsst-sqre/charts/blob/master/charts/strimzi-registry-operator/README.md).

### With Kustomize

The manifests for the operator itself are located in the `/manifests` directory of this repository.
You can use Kustomize to build a single YAML file for deployment:

```sh
kustomize build manifests > manifest.yaml
kubectl apply -f manifest.yaml
```

The `strimzi-registry-operator` expects environment variables to be configured at deployment time to determine which Kafka cluster and namespace it should watch.
The patch file allows you to set these values without modifying the original manifests.

```txt
overlay/
├── kustomization.yaml
└── strimzi-registry-operator-deployment.yaml
```

A basic ``kustomization.yaml`` file is:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - github.com/lsst-sqre/strimzi-registry-operator.git//manifests?ref=0.7.0

patches:
  - strimzi-registry-operator-deployment.yaml
```

Use the `strimzi-registry-operator-deployment.yaml` patch to set environment variables:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: strimzi-registry-operator
spec:
  template:
    spec:
      containers:
        - name: operator
          env:
            - name: SSR_CLUSTER_NAME
              value: events
            - name: SSR_NAMESPACE
              value: events
```

- `SSR_CLUSTER_NAME` is the name of the Strimzi Kafka cluster.
- `SSR_NAMESPACE` is the namespace where the Strimzi Kafka cluster is deployed and where the `StrimziSchemaRegistry`, `KafkaUser` and `KafkaTopic` resources are found.

## Deploy a Schema Registry

The following resources must be deployed in the same namespace as your Kafka cluster.

### Step 1. Deploy a KafkaTopic

Create a `KafkaTopic` resource for the Schema Registry's primary storage.

```yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaTopic
metadata:
  name: registry-schemas
  labels:
    strimzi.io/cluster: events
spec:
  # Actual Kafka topic name will match `metadata.name` unless `spec.topicName` is set.
  partitions: 1
  replicas: 3
  config:
    # Schema Registry requires log compaction to ensure that the the latest version of each schema is always retained
    cleanup.policy: compact
```

> **Notes**
>
>The name `registry-schemas` is used here instead of the Confluent default `_schemas` because underscores (_) are not valid in Kubernetes resource names, and thus cannot be used in `metadata.name`.
>If you want to keep the actual Kafka topic name as `_schemas`, you can set:
>```yaml
>spec:
>  topicName: _schemas
>```
>while keeping a Kubernetes-safe `metadata.name`.
>
>You can configure a different Schema Registry topic name in the `StrimziSchemaRegistry` resource via its configuration properties.
>Stick to lowercase, alphanumeric, and hyphen (-) characters in `metadata.name` for maximum compatibility.

### Step 2. Deploy a KafkaUser

Deploy a `KafkaUser` for the Schema Registry that gives the Schema Registry sufficient permissions:

```yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaUser
metadata:
  name: confluent-schema-registry
  labels:
    strimzi.io/cluster: events
spec:
  authentication:
    type: tls
  authorization:
    # Official docs on authorizations required for the Schema Registry:
    # https://docs.confluent.io/current/schema-registry/security/index.html#authorizing-access-to-the-schemas-topic
    type: simple
    acls:
      # Allow all operations on the registry-schemas topic
      # Read, Write, and DescribeConfigs are known to be required
      - resource:
          type: topic
          name: registry-schemas
          patternType: literal
        operations:
          - All
        type: allow
      # Allow all operations on the schema-registry* group
      - resource:
          type: group
          name: schema-registry
          patternType: prefix
        operations:
          - All
        type: allow
      # Allow Describe on the __consumer_offsets topic
      - resource:
          type: topic
          name: __consumer_offsets
          patternType: literal
        operations:
          - Describe
        type: allow
```

> **Note**
> Since the `KafkaUser` is configured with `authorization.type: simple` make sure your kafka cluster has this option enabled.
> ```yaml
> apiVersion: kafka.strimzi.io/v1beta2
> kind: Kafka
> metadata:
>   name: events
> spec:
>   kafka:
>     # ...
>     authorization:
>       type: simple
> ```

### Step 3. Deploy the StrimziSchemaRegistry

Now that there is a topic and a user, you can deploy the Schema Registry itself.
The strimzi-schema-registry operator deploys the Schema Registry given a `StrimziSchemaRegistry` resource:

```yaml
apiVersion: roundtable.lsst.codes/v1beta1
kind: StrimziSchemaRegistry
metadata:
  name: confluent-schema-registry
  labels:
    strimzi.io/cluster: events
spec:
  strimziVersion: v1beta2
  listener: tls
```

The section [StrimziSchemaRegistry configuration properties](#strimzischemaregistry-configuration-properties) describes the configuration properties for the `StrimziSchemaRegistry`.

## Access the Schema Registry API

By default, the operator creates a Kubernetes Service of type `ClusterIP` named after your `StrimziSchemaRegistry` resource. The Service exposes the Schema Registry HTTP API on port 8081 and is reachable from inside the cluster.

For the `StrimziSchemaRegistry` resource configured in step 3 above, the URL to access the Schema Registry API will be `http://confluent-schema-registry.events.svc.cluster.local:8081`.

You can check the deployment by hitting the API from a Pod in the same cluster/namespace:

```bash
kubectl -n events run -it --rm curl --image=curlimages/curl --restart=Never -- \
  curl -s http://confluent-schema-registry.events.svc.cluster.local:8081/subjects
```

If you prefer a node-level endpoint, the operator can create a `NodePort` Service (see the `serviceType` configuration property).
Enabling `NodePort` depends on your cluster policies.
In production, keep the default `ClusterIP` and use an ingress in front of it for external access.

## StrimziSchemaRegistry configuration properties

These configurations can be set as fields of the `StrimziSchemaRegistry`'s `spec` field:

```yaml
apiVersion: roundtable.lsst.codes/v1beta1
kind: StrimziSchemaRegistry
metadata:
  name: confluent-schema-registry
  labels:
    strimzi.io/cluster: events
spec:
  strimziVersion: v1beta2
  listener: tls
  securityProtocol: tls
  compatibilityLevel: forward
  registryTopic: "registry-schemas"
  registryImage: confluentinc/cp-schema-registry
  registryImageTag: "8.0.0"
  replicas: 1
  serviceType: ClusterIP
  cpuLimit: ""
  cpuRequest: ""
  memoryLimit: ""
  memoryRequest: ""
```

### Strimzi-related configurations

- `strimziVersion` is the version of the `kafka.strimzi.io` Custom Resource API to use.
  The correct value depends on the deployed version of Strimzi.
  The current Strimzi API  version is `v1beta2`.

### Schema Registry-related configurations

- `listener` is the **name** of the Kafka listener that the Schema Registry should use.
  The default value is `tls`, but you should set this value based on your `Kafka` resource.
  The ["In-detail: listener configuration"](#in-detail-listener-configuration) section, below, explains this in more detail.
  See also: Schema Registry [listeners](https://docs.confluent.io/platform/current/schema-registry/installation/config.html#listeners) docs.

- `securityProtocol` is the security protocol for the Schema Registry to communicate with Kafka. Default is SSL. Can be:

  - `SSL`
  - `PLAINTEXT`
  - `SASL_PLAINTEXT`
  - `SASL_SSL`

  See also: Schema Registry [kafkastore.security.protocol](https://docs.confluent.io/platform/current/schema-registry/installation/config.html#kafkastore-security-protocol) docs.

- `compatibilityLevel` is the default schema compatibility level. Default is "forward". Possible values:

  - `none`
  - `backward`
  - `backward_transitive`
  - `forward`
  - `forward_transitive`
  - `full`
  - `full_transitive`

  See also: Schema Registry [schema.compatibility.level](https://docs.confluent.io/platform/current/schema-registry/installation/config.html#schema-compatibility-level) docs.

- `registryTopic` is the name of the Kafka topic used by the Schema Registry to store schemas.
  Default is `registry-schemas`.

  See also the notes in the **Deploy a KafkaTopic** section above.

### Kubernetes configurations for the Schema Registry

- `registryImage` is the name of the Confluent Schema Registry Docker image (without the tag).
  Default is `confluentinc/cp-schema-registry`.

- `registryImageTag` is the name of the Schema Registry Docker image's tag.
  Use this property to change the version of the Confluent Schema Registry that you're deploying through the `StrimziSchemaRegistry`.
  Default is `8.0.0`.

- `replicas` is the number of replicas for the Schema Registry deployment.
  Default is 1.

- `serviceType` is the type of service to create for the registry. Default is ClusterIP. Can be NodePort to publish the registry externally.

- `cpuLimit` is the cap on CPU usage for the Schema Registry container. Default is to leave unset. Example `1000m` limits to 1 CPU.

- `cpuRequest` is the requested CPU for the Schema Registry container. Default is to leave unset. Example: `100m` requests 0.1 CPU.

- `memoryLimit` is the cap on memory usage for the Schema Registry container. Default is to leave unset. Example `1000M` limits to 1000 megabytes.

- `memoryRequest` is the requested memory for the Schema Registry container. Default is to leave unset. Example: `768M` requests 768 megabytes.

### In detail: listener configuration

The `spec.listener` field in the `StrimziSchemaRegistry` resource specifies the Kafka broker listener that the Schema Registry uses.
These listeners are configured in the `Kafka` resource you created with Strimzi.

Consider a `Kafka` resource:

```yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: Kafka
metadata:
  name: my-cluster
spec:
  kafka:
    #...
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
      - name: external2
        port: 9095
        type: ingress
        tls: true
        authentication:
          type: tls
        configuration:
          bootstrap:
            host: bootstrap.myingress.com
          brokers:
          - broker: 0
            host: broker-0.myingress.com
          - broker: 1
            host: broker-1.myingress.com
          - broker: 2
            host: broker-2.myingress.com
    #...
```

To use the encrypted internal listener, the `spec.listener` field in your `StrimziSchemaRegistry` resource should be `tls`:

```yaml
apiVersion: roundtable.lsst.codes/v1beta1
kind: StrimziSchemaRegistry
metadata:
  name: confluent-schema-registry
spec:
  listener: tls
```

To use the unencrypted internal listener instead, the `spec.listener` field in your `StrimziSchemaRegistry` resource should be `plain` instead:

```yaml
apiVersion: roundtable.lsst.codes/v1beta1
kind: StrimziSchemaRegistry
metadata:
  name: confluent-schema-registry
spec:
  listener: plain
```

### Strimzi `v1beta1` listener configuration

In older versions of Strimzi with the `v1beta1` API, listeners were not named.
Instead, three types of listeners were available:

```yaml
apiVersion: kafka.strimzi.io/v1beta1
kind: Kafka
spec:
  kafka:
    # ...
    listeners:
      plain: {}
      tls:
        authentication:
          type: "tls"
      external: {}
```

In this case, set the `spec.listener` field in your `StrimziSchemaRegistry` to either `plain`, `tls`, or `external`.
