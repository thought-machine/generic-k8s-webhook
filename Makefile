SRC_DIR := ./generic_k8s_webhook
TEST_DIR := ./tests
SRC_FILES := $(shell find $(SRC_DIR) -type f -name '*.py')
TEST_FILES := $(shell find $(TEST_DIR) -type f -name '*.py' -o -name '*.yaml')

out/install-deps.stamp: pyproject.toml poetry.lock
	poetry install
	mkdir -p out
	touch out/install-deps.stamp

install-deps: out/install-deps.stamp

out/build.stamp: install-deps $(SRC_FILES) $(TEST_FILES)
	poetry build
	touch out/build.stamp

build: out/build.stamp

.PHONY: lint
lint: build
	poetry run isort $(SRC_DIR) $(TEST_DIR) -c
	poetry run black $(SRC_DIR) $(TEST_DIR) --check
	poetry run pylint $(SRC_DIR) -v

.PHONY: format
format: build
	poetry run isort $(SRC_DIR) $(TEST_DIR)
	poetry run black $(SRC_DIR) $(TEST_DIR)

.PHONY: unittests
unittests: build
	poetry run pytest tests --cov=generic_k8s_webhook
	poetry run coverage html

.PHONY: check-pyproject
check-pyproject:
	echo "Check the pyproject.toml has 'version = \"0.0.0\"'"
	grep 'version = "0.0.0"' pyproject.toml

.PHONY: docker
docker:
	docker build -t generic-k8s-webhook:latest .

all-tests: check-pyproject lint unittests docker

all-tests-seq: | check-pyproject lint unittests docker
