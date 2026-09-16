#!/usr/bin/env bash

set -Eeuo pipefail
set -x

# Deploy strimzi registry operator using kustomized configuration

dump_operator_diagnostics() {
    local status=$?

    trap - ERR
    set +e
    kubectl get pods -n default -l app=strimzi-registry-operator -o wide
    kubectl describe deployment/strimzi-registry-operator -n default
    kubectl describe pods -n default -l app=strimzi-registry-operator
    kubectl logs -n default deployment/strimzi-registry-operator \
        --all-containers
    kubectl logs -n default deployment/strimzi-registry-operator \
        --all-containers --previous
    kubectl get events -n default --sort-by=.lastTimestamp
    minikube image ls
    exit "$status"
}

trap dump_operator_diagnostics ERR

kustomize build operator-deployment | kubectl apply -f -
kubectl wait -n default deployment strimzi-registry-operator \
    --for condition=Available=True --timeout=300s
sleep 5s
kubectl get crds
kubectl get deployments
