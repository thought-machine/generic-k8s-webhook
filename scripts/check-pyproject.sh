#!/bin/bash

set -e

SCRIPTPATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"
REPOROOT_PATH="$SCRIPTPATH/.."

echo "Check the $REPOROOT_PATH/pyproject.toml has 'version = \"0.0.0\"'"
grep 'version = "0.0.0"' pyproject.toml
