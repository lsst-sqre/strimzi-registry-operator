#!/usr/bin/env bash

set -euo pipefail
set -x

# Build the strimzi-registry-operator docker image inside minikube
# Based on https://minikube.sigs.k8s.io/docs/tutorials/setup_minikube_in_github_actions/
eval "$(minikube -p minikube docker-env)"
docker build -f ../Dockerfile -t local/strimzi-registry-operator ../
docker image inspect local/strimzi-registry-operator:latest >/dev/null
