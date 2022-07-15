#########################
strimzi-registry-operator
#########################

A Kubernetes Operator for running the `Confluent Schema Registry <https://docs.confluent.io/current/schema-registry/index.html>`_ in a `Strimzi <https://strimzi.io>`_-based `Kafka <https://kafka.apache.org/>`_ cluster that's secured with TLS.

Overview:

- Once you deploy a ``StrimziSchemaRegistry`` manifest, the operator creates a Kubernetes deployment of the Confluent Schema Registry, along with an associated Kubernetes service and secret.
- Works with Strimzi's TLS authentication and authorization by converting the TLS certificate associated with a KafkaUser into a JKS-formatted keystore and truststore that's used by Confluence Schema Registry.
- When Strimzi updates either the Kafka cluster's CA certificate or the KafkaUser's client certificates, the operator automatically recreates the JKS truststore/keystore secrets and triggers a rolling restart of the Schema Registry pods.

Deploy the operator
===================

There are two steps for running strimzi-registry-operator. First, you'll need to deploy the operator itself --- this is described in this section.
Once the operator is deployed, you can deploy ``StrimziSchemaRegistry`` resources that actually create and maintain a Confluent Schema Registry application (this is discussed in later sections).

Two operator deployment options are available: `Helm <https://helm.sh>`__ and `Kustomize <https://kustomize.io>`__.

With Helm
---------

A Helm chart is available for strimzi-registry-operator on GitHub at `lsst-sqre/charts <https://github.com/lsst-sqre/charts/tree/master/charts/strimzi-registry-operator>`__.

.. code-block:: sh

   helm repo add lsstsqre https://lsst-sqre.github.io/charts/
   helm repo update
   helm install lsstsqre/strimzi-registry-operator --name ssr --set watchNamespace="...",clusterName="..."

`See the Helm chart's README <lsst-sqre/charts <https://github.com/lsst-sqre/charts/tree/master/charts/strimzi-registry-operator>`__ for important values to set, including the names of the Strimzi Kafka cluster and namespace for KafkaUser resources to watch.

With Kustomize
--------------

The manifests for the operator itself are located in the `/manifests` directory of this repository.
You can use Kustomize to build a single YAML file for deployment.::

    kustomize build manifests > manifest.yaml
    kubectl apply -f manifest.yaml

To configure the name of the Strimzi cluster and the namespace where KafkaUser resources are available, you'll need to create your own Kustomize overlay.

A basic ``kustomization.yaml`` file is:

.. code-block:: yaml

   apiVersion: kustomize.config.k8s.io/v1beta1
   kind: Kustomization

   resources:
     - github.com/lsst-sqre/strimzi-registry-operator.git//manifests?ref=0.4.1

   patches:
     - strimzi-registry-operator-deployment.yaml

Use the ``strimzi-registry-operator-deployment.yaml`` patch to set environment variables:

.. code-block:: yaml

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

- ``SSR_CLUSTER_NAME`` is the name of the Strimzi Kafka cluster.
- ``SSR_NAMESPACE`` is the namespace where the Strimzi Kafka cluster is deployed and where KafkaUser resources are found.

Deploy a Schema Registry
========================

Step 1. Deploy a KafkaTopic
---------------------------

Deploy a ``KafkaTopic`` that the Schema Registry will use as its primary storage.

.. code-block:: yaml

   apiVersion: kafka.strimzi.io/v1beta2
   kind: KafkaTopic
   metadata:
     name: registry-schemas
     labels:
       strimzi.io/cluster: events
   spec:
     partitions: 1
     replicas: 3
     config:
       # http://kafka.apache.org/documentation/#topicconfigs
       cleanup.policy: compact

.. important::

   The name ``registry-schemas`` is currently required.
   The default name, ``_schemas`` isn't used because it isn't convenient to create with ``KafkaTopic`` resources.

Step 2. Deploy a KafkaUser
--------------------------

Deploy a KafkaUser for the Schema Registry that gives the Schema Registry sufficient permissions:

.. code-block:: yaml

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
         # Allow all operations on the _schemas topic
         # Read, Write, and DescribeConfigs are known to be required
         - resource:
             type: topic
             name: registry-schemas
             patternType: literal
           operation: All
           type: allow
         # Allow all operations on the schema-registry* group
         - resource:
             type: group
             name: schema-registry
             patternType: prefix
           operation: All
           type: allow
         # Allow Describe on the __consumer_offsets topic
         # (The official docs also mention DescribeConfigs?)
         - resource:
             type: topic
             name: __consumer_offsets
             patternType: literal
           operation: Describe
           type: allow

Step 3. Deploy the StrimziSchemaRegistry
----------------------------------------

Now that there is a topic and a user, you can deploy the Schema Registry itself.
The strimzi-schema-registry operator deploys the Schema Registry given a ``StrimziSchemaRegistry`` resource:

.. code-block:: yaml

   apiVersion: roundtable.lsst.codes/v1beta1
   kind: StrimziSchemaRegistry
   metadata:
     name: confluent-schema-registry
   spec:
     strimzi-version: v1beta2
     listener: tls

- ``strimzi-version`` is the version of the ``kafka.strimzi.io`` Custom Resource API to use.
  The correct value depends on the deployed version of Strimzi.
- ``listener`` is the Kafka listener that the Schema Registry should use.
  Available values: ``plain``, ``tls`` and ``external``.
