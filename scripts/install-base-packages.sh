#!/bin/bash

# This script updates packages in the base Docker image that's used by both the
# build and runtime images, and gives us a place to install additional
# system-level packages with apt-get.
#
# Based on the blog post:
# https://pythonspeed.com/articles/system-packages-docker/

# Bash "strict mode", to help catch problems and bugs in the shell
# script. Every bash script you write should include this. See
# http://redsymbol.net/articles/unofficial-bash-strict-mode/ for
# details.
set -euo pipefail

# Display each command as it's run.
set -x

# Tell apt-get we're never going to be able to give manual
# feedback:
export DEBIAN_FRONTEND=noninteractive

# Update the package listing, so we know what packages exist:
apt-get update

# Install security updates:
apt-get -y upgrade

# Example of installing a new package, without unnecessary packages:
# default-jre needed for keytool
apt-get -y install --no-install-recommends git default-jre

# Delete cached files we don't need anymore:
apt-get clean
rm -rf /var/lib/apt/lists/*
