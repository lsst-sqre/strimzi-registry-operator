#!/bin/bash

set -ex

# Manage the image push to Docker Hub from Travis CI. The image is tagged
# with the branch or tag name being built by Travis.
#
# travis-docker-deploy.sh <image_name> <built_tag>

# Skip deployments in PRs
if [ $TRAVIS_PULL_REQUEST != "false" ]; then
    exit 0;
fi

# Only build DEPLOY_DOCKER_IMAGE is explicitly set in .travis.yml.
if [ $DEPLOY_DOCKER_IMAGE == "false" ]; then
    echo "Skipping docker build. \$DEPLOY_DOCKER_IMAGE=false";
    exit 0;
fi

docker login -u "$DOCKER_USERNAME" -p "$DOCKER_PASSWORD";

IMAGE_NAME=$1;
BASE_TAG=$2;

# Create tag; latest for master; otherwise use branch name
if [ "$TRAVIS_BRANCH" == "master" ]; then
    TAG="latest";

else
    # need to sanitize any "/" from git branches
    TAG=`echo "$TRAVIS_BRANCH" | sed "s/\//-/g"`;
fi

# Tag and push the branch-based name
docker tag ${IMAGE_NAME}:${BASE_TAG} ${IMAGE_NAME}:${TAG}
docker push ${IMAGE_NAME}:${TAG}
