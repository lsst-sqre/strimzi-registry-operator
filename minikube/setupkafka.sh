#!/usr/bin/env bash

set -x

# Deploy a Strimzi Kafka
# testregistryapi.sh strimzi-version
#
# Positional argumennts:
# - strimzi-version is the version of strimzi to use
#
# Example:
# ./testregistryapi.sh 0.29.0

# Download Strimzi release with Kubernetes manifests
curl -L0 https://github.com/strimzi/strimzi-kafka-operator/releases/download/$1/strimzi-$1.tar.gz | tar xvz

# Configure Strimzi to watch a single namespace
# https://strimzi.io/docs/operators/latest/deploying.html#deploying-cluster-operator-str
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS version of sed command
    sed -i '' 's/namespace: .*/namespace: default/' \
        strimzi-$1/install/cluster-operator/*RoleBinding*.yaml
else
    # General linux version of sed command
    sed -i 's/namespace: .*/namespace: default/' \
        strimzi-$1/install/cluster-operator/*RoleBinding*.yaml
fi

# Deploy Strimzi Cluster Operator
kubectl apply -f strimzi-$1/install/cluster-operator -n default
kubectl wait -n default deployment strimzi-cluster-operator --for condition=Available=True --timeout=600s

# Deploy a Kafka cluster
kubectl apply -f kafka.yaml -n default
kubectl wait kafka/test-cluster --for=condition=Ready --timeout=300s
