#!/bin/bash

set -e

SCRIPTPATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"


cd "$SCRIPTPATH/.."
echo "Running linter"
./scripts/format-code.sh --check
echo "Running unittests and e2e tests"
poetry run pytest tests
echo "Building docker container"
docker build -t generic-k8s-webhook:latest .
