#!/bin/bash

set -e

SCRIPTPATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

if [ ! "$1" = "--check" ]
then
    NO_CHECK="true"
fi

cd "$SCRIPTPATH/.."
poetry run isort generic_k8s_webhook/ "${NO_CHECK:--c}"
poetry run black generic_k8s_webhook/ "${NO_CHECK:---check}"
if [ -z "$NO_CHECK" ]
then
    poetry run pylint generic_k8s_webhook/ -E
    poetry run pylint generic_k8s_webhook/ -v --fail-under=9.5
fi
