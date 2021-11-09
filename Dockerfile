FROM python:3.7.4-buster

MAINTAINER LSST SQuaRE <sqre-admin@lists.lsst.org>
LABEL description="Kubernetes operator that deploys the Confluent Schema Registry in a Strimzi-based Kafka cluster where TLS authentication and authorization is enabled." \
      name="lsstsqre/strimzi-registry-operator"

# Need the JRE for keytool
RUN apt-get update && apt-get install -y --no-install-recommends \
        default-jre \
    && rm -rf /var/lib/apt/lists/*

ENV APPDIR /app
RUN mkdir $APPDIR
WORKDIR $APPDIR

# Supply on CL as --build-arg VERSION=<version> (or run `make image`).
ARG VERSION
LABEL version="$VERSION"

# Must run python setup.py sdist first before building the Docker image.

COPY dist/strimzi-registry-operator-$VERSION.tar.gz .
RUN pip install strimzi-registry-operator-$VERSION.tar.gz && \
    rm strimzi-registry-operator-$VERSION.tar.gz && \
    groupadd -r app_grp && useradd -r -g app_grp app && \
    chown -R app:app_grp $APPDIR

USER app

# Accept the SSR_NAMESPACE env var for a namespace to watch, defaulting to 'events'.
CMD ["sh", "-c", "kopf run --standalone -m strimziregistryoperator.handlers --namespace ${SSR_NAMESPACE:-events} --verbose"]
