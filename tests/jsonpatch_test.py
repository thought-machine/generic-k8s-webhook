import os

import pytest
import yaml
from test_utils import expand_schemas

from generic_k8s_webhook.config_parser.entrypoint import GenericWebhookConfigManifest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSONPATCH_YAML = os.path.join(SCRIPT_DIR, "jsonpatch_test.yaml")


def _parse_tests() -> list[tuple]:
    with open(JSONPATCH_YAML, "r") as f:
        raw_tests = yaml.safe_load(f)

    parsed_tests = []
    for test_suite in raw_tests["test_suites"]:
        for test in test_suite["tests"]:
            for schema in expand_schemas(raw_tests["schemas_subsets"], test["schemas"]):
                for i, case in enumerate(test["cases"]):
                    parsed_tests.append(
                        (
                            f"{test_suite['name']}_{i}",  # name
                            schema,  # schema
                            case["patch"],  # patch
                            case["payload"],  # payload
                            case["expected_result"],  # expected_result
                        )
                    )
    return parsed_tests


@pytest.mark.parametrize(("name", "schema", "patch", "payload", "expected_result"), _parse_tests())
def test_all(name, schema, patch, payload, expected_result):
    raw_config = {
        "apiVersion": f"generic-webhook/{schema}",
        "kind": "GenericWebhookConfig",
        "webhooks": [{"name": "test-webhook", "path": "test-path", "actions": [{"patch": [patch]}]}],
    }
    gwcm = GenericWebhookConfigManifest(raw_config)
    action = gwcm.list_webhook_config[0].list_actions[0]
    json_patch = action.get_patches(payload)
    result = json_patch.apply(payload)
    assert result == expected_result
