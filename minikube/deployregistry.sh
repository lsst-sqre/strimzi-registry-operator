#!/usr/bin/env bash

set -x

# Deploy a StrimziSchemaRegistry, along with the Kafka user and topics
# required for it.
#
# Example:
# ./deployregistry.sh

# Deploy Kafka Topic for Schema Registry
kubectl apply -f registry-topic.yaml -n default
kubectl wait kafkatopic/registry-schemas --for=condition=Ready --timeout=300s

# Deploy Kafka User for Schema Registry
kubectl apply -f registry-user.yaml -n default
kubectl wait kafkauser/confluent-schema-registry --for=condition=Ready --timeout=300s

sleep 5s

kubectl apply -f schema-registry.yaml
sleep 10s # wait for registry-operator to create deployment
kubectl wait -n default deployment confluent-schema-registry \
    --for condition=Available=True --timeout=600s
