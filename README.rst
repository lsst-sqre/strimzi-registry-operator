#########################
strimzi-registry-operator
#########################

A Kubernetes Operator for running the `Confluent Schema Registry <https://docs.confluent.io/current/schema-registry/index.html>`_ in a `Strimzi <https://strimzi.io>`_-based `Kafka <https://kafka.apache.org/>`_ cluster that's secured with TLS.

Overview:

- Once you deploy a ``StrimziSchemaRegistry`` manifest, the operator creates a Kubernetes deployment of the Confluent Schema Registry, along with an associated Kubernetes service and secret.
- Works with Strimzi's TLS authentication and authorization by converting the TLS certificate associated with a KafkaUser into a JKS-formatted keystore and truststore that's used by Confluence Schema Registry.
- When Strimzi updates either the Kafka cluster's CA certificate or the KafkaUser's client certificates, the operator automatically recreates the JKS truststore/keystore secrets and triggers a rolling restart of the Schema Registry pods.

**This operator is still in early development and testing.
It probably isn't suitable for use outside LSST at the moment.**

Deploy the operator
===================

The manifests for the operator itself are located in the `/manifests` directory of this repository.
You can use Kustomize to build a single YAML file for deployment.::

    kustomize build manifests > manifest.yaml
    kubectl apply -f manifest.yaml

You can also create your own overay to customize details such as namespace and the name of the Docker image.

Deploy a Schema Registry
========================

Step 1. Deploy a KafkaTopic
---------------------------

Deploy a ``KafkaTopic`` that the Schema Registry will use as its primary storage.

.. code-block:: yaml

   apiVersion: kafka.strimzi.io/v1beta1
   kind: KafkaTopic
   metadata:
     name: "registry-schemas"
     labels:
       strimzi.io/cluster: events
   spec:
     partitions: 1
     replicas: 3
     config:
       # http://kafka.apache.org/documentation/#topicconfigs
       cleanup.policy: "compact"

.. important::

   The name ``registry-schemas`` is currently required.
   The default name, ``_schemas`` isn't used because it isn't convenient to create with ``KafkaTopic`` resources.

Step 2. Deploy a KafkaUser
--------------------------

Deploy a KafkaUser for the Schema Registry that gives the Schema Registry sufficient permissions:

.. code-block:: yaml

   apiVersion: kafka.strimzi.io/v1beta1
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
             name: "registry-schemas"
             patternType: literal
           operation: All
           type: allow
         # Allow all operations on the schema-registry* group
         - resource:
             type: group
             name: "schema-registry"
             patternType: prefix
           operation: All
           type: allow
         # Allow Describe on the __consumer_offsets topic
         # (The official docs also mention DescribeConfigs?)
         - resource:
             type: topic
             name: "__consumer_offsets"
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
   spec: {}
