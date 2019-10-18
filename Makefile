.PHONY: install
install:
	pip install -e ".[dev]"

.PHONY: test
test:
	pytest

.PHONY: image
image:
	python setup.py sdist
	docker build --build-arg VERSION=`python -m strimziregistryoperator.version` -t lsstsqre/strimzi-registry-operator:build .

.PHONY: travis-docker-deploy
travis-docker-deploy:
	./bin/travis-docker-deploy.sh lsstsqre/strimzi-registry-operator build

.PHONY: version
version:
	python -m strimziregistryoperator.version
