# Contributor guide

## Required tools

- [Git](https://git-scm.com/downloads)
- [Python 3.10+](https://www.python.org/downloads/)
- [Poetry](https://python-poetry.org/docs/)
- [Docker](https://docs.docker.com/install/)

## Run

The app can be executed locally (without the need of installing it) using two different modes: server and cli.

In server mode, it creates an http(s) server that answers to [K8S admission review requests](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/#webhook-request-and-response).

```bash
# Create http server (no TLS)
poetry run python3 generic_k8s_webhook/main.py --config <GenericWebhookConfigFile> server --port <port>

# Create http server with TLS
poetry run python3 generic_k8s_webhook/main.py --config <GenericWebhookConfigFile> server --port <port> --cert-file <cert.pem> --key-file <key.pem>
```

In cli mode, it consumes a K8S manifest as input and outputs if the manifest is accepted according to the webhook config and it also show the modified manifest, in case the webhook is configure to mutate it.

```bash
poetry run python3 generic_k8s_webhook/main.py --config <GenericWebhookConfigFile> cli --k8s-manifest <k8s-manifest.yaml> --wh-name <name>
```

## Format code

The project uses [black](https://black.readthedocs.io/en/stable/) and [isort](https://pycqa.github.io/isor) to format the code. To do so automatically, you can run this script:

```bash
./scripts/format-code.sh
```

## Test

You can run all the tests executed in the CI by calling:

```bash
./scripts/run-all-tests.sh
```

These tests can be splitted in 3 categories.

### Linter

The linting phase checks that the code is well [formatted](#format-code). Apart from that, it also runs [pylint](https://www.pylint.org/). In order to pass the linting phase, `pylint` must not detect any error and must give an overall score of >9.5.

```bash
./scripts/format-code.sh --check
```

### Unittests and e2e tests

We use [pytest](https://docs.pytest.org/en/7.3.x/) to test the functionality of the app. These tests are defined under the [tests](../tests/) directory and they are a mix of both pure unittests and end-to-end tests.

```bash
poetry run pytest tests
```

### Docker build

The last phase of our testing suite is building the docker container that has our app installed in it.

```bash
docker build -t generic-k8s-webhook:latest .
```

## Structure of the code

The [webhook.py](../generic_k8s_webhook/webhook.py) contains the classes that implement the configuration specified in a `<GenericWebhookConfigFile>`. For example, the class `Webhook` implements a given element from the list `webhooks` from the config yaml file. The class `Action` implements a given element from the list `actions`. The [operators.py](../generic_k8s_webhook/operators.py) contains the classes that implement the operators used to specify conditions in the webhook config.

However, none of these classes have a direct dependency to the structure of the `<GenericWebhookConfigFile>`. The glue between them can be found in [config_parser.py](../generic_k8s_webhook/config_parser.py). This file contains the classes that parse the `<GenericWebhookConfigFile>`, check its structure is valid, resolves the default values and, finally, generates the corresponding object (a class from `webhook.py` or `operators.py`).

In case you want to add a new operator, you need to create a new class in `config_parser.py` to parse it and another class in `operators.py` to implement its logic.

This structure helps decoupling the `<GenericWebhookConfigFile>` from the core of the app, so new versions of the schema corresponding to `<GenericWebhookConfigFile>` won't need a complete rewrite of our code.
