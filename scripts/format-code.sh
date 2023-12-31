#!/bin/bash

set -e

SCRIPTPATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

if [ "$1" = "--check" ]
then
    CHECK=true
else
    CHECK=false
fi

cd "$SCRIPTPATH/.."
poetry run isort generic_k8s_webhook/ tests/ $($CHECK && echo "-c")
poetry run black generic_k8s_webhook/ tests/ $($CHECK && echo "--check")
if $CHECK
then
    poetry run pylint generic_k8s_webhook/ -E
    poetry run pylint generic_k8s_webhook/ -v --fail-under=9.5
fi
