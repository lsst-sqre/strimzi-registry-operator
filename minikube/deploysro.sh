#!/usr/bin/env bash

set -x

# Deploy strimzi registry operator using kustomized configuration

kustomize build operator-deployment | kubectl apply -f -
kubectl wait -n default deployment strimzi-registry-operator \
--for condition=Available=True --timeout=600s
sleep 5s
kubectl get crds
kubectl get deployments
