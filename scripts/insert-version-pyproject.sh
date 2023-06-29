#!/bin/bash

set -e

SCRIPTPATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"
REPOROOT_PATH="$SCRIPTPATH/.."

NEW_VERSION=$1

sed -i "s/version = \"0.0.0\"/version = \"$NEW_VERSION\"/g" "$REPOROOT_PATH/pyproject.toml"
