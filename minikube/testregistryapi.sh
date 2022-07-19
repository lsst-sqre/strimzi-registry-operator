#!/usr/bin/env bash

set -x

# Simple exercise of the Schema Registry's API to demonstrate functionality
# testregistryapi.sh registry-name
#
# Positional argumennts:
# - registry-name is the name of the StrimziSchemaRegistry to connect to
#
# Example:
# ./testregistryapi.sh confluent-schema-registry

# Create a connection to the NodePort service in Minikube
minikube service list
minikube service $1 --url
echo "------------------opening the service------------------"
echo $(minikube service $1 --url)
# Pause for service to stablilize
sleep 30s

# Get URL for registry service
export REGISTRY_URL=$(minikube service $1 --url)
echo $REGISTRY_URL
sleep 1s

# Test call to the registry's /config endpoint
http --ignore-stdin get $REGISTRY_URL/config
sleep 1s

# Post a new schema to the registry
http --ignore-stdin --json post $REGISTRY_URL/subjects/testsubject/versions \
    schema=@testsubject.json \
    Accept:application/vnd.schemaregistry.v1+json
sleep 1s

# Get schema back
http --ignore-stdin --json get $REGISTRY_URL/subjects/testsubject/versions/1 \
    Accept:application/vnd.schemaregistry.v1+json
