#!/usr/bin/env bash

set -Eeuo pipefail
set -x

# Deploy a StrimziSchemaRegistry, along with the Kafka user and topics
# required for it.
#
# Example:
# ./deployregistry.sh

dump_registry_diagnostics() {
    local status=$?

    trap - ERR
    set +e
    kubectl get kafkatopic/registry-schemas -n default -o yaml
    kubectl get kafkauser/confluent-schema-registry -n default -o yaml
    kubectl get \
        strimzischemaregistry/confluent-schema-registry \
        -n default -o yaml
    kubectl get \
        poddisruptionbudget/confluent-schema-registry \
        -n default -o yaml
    kubectl get deployments,pods -n default -o wide
    kubectl describe deployment/confluent-schema-registry -n default
    kubectl logs -n default deployment/strimzi-registry-operator \
        --all-containers
    kubectl get events -n default --sort-by=.lastTimestamp
    exit "$status"
}

trap dump_registry_diagnostics ERR

# Deploy Kafka Topic for Schema Registry
kubectl apply -f registry-topic.yaml -n default
kubectl wait -n default kafkatopic/registry-schemas \
    --for=condition=Ready --timeout=300s

# Deploy Kafka User for Schema Registry
kubectl apply -f registry-user.yaml -n default
kubectl wait -n default kafkauser/confluent-schema-registry \
    --for=condition=Ready --timeout=300s

sleep 5s

kubectl apply -f schema-registry.yaml -n default
kubectl wait -n default --for=create \
    deployment/confluent-schema-registry --timeout=300s
kubectl wait -n default --for=create \
    poddisruptionbudget/confluent-schema-registry --timeout=300s
kubectl rollout status -n default \
    deployment/confluent-schema-registry --timeout=600s
test "$(kubectl get -n default deployment/confluent-schema-registry \
    -o jsonpath='{.spec.replicas}')" = "2"
test "$(kubectl get -n default deployment/confluent-schema-registry \
    -o jsonpath='{.status.availableReplicas}')" = "2"
kubectl wait -n default \
    poddisruptionbudget/confluent-schema-registry \
    --for=jsonpath='{.status.disruptionsAllowed}'=1 --timeout=300s
kubectl get deployments,pods -n default -o wide
kubectl get poddisruptionbudgets -n default
