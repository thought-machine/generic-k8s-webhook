import os

import pytest
import yaml

from generic_k8s_webhook.config_parser.entrypoint import GenericWebhookConfigManifest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONDITIONS_YAML = os.path.join(SCRIPT_DIR, "conditions_test.yaml")


def _expand_schemas(schemas_subsets: dict[str, list[str]], list_schemas: list[str]) -> list[str]:
    final_schemas = set()
    for schema in list_schemas:
        final_schemas.add(schema)
        for schemas_superset in schemas_subsets.get(schema, []):
            final_schemas.add(schemas_superset)
    return sorted(list(final_schemas))


def _parse_tests() -> list[tuple]:
    with open(CONDITIONS_YAML, "r") as f:
        raw_tests = yaml.safe_load(f)

    parsed_tests = []
    for test_suite in raw_tests["test_suites"]:
        for test in test_suite["tests"]:
            for schema in _expand_schemas(raw_tests["schemas_subsets"], test["schemas"]):
                for i, case in enumerate(test["cases"]):
                    parsed_tests.append(
                        (
                            f"{test_suite['name']}_{i}",  # name
                            schema,  # schema
                            case["condition"],  # condition
                            case.get("context", [{}]),  # context
                            case["expected_result"],  # expected_result
                        )
                    )
    return parsed_tests


@pytest.mark.parametrize(("name", "schema", "condition", "context", "expected_result"), _parse_tests())
def test_all(name, schema, condition, context, expected_result):
    raw_config = {
        "apiVersion": f"generic-webhook/{schema}",
        "kind": "GenericWebhookConfig",
        "webhooks": [{"name": "test-webhook", "path": "test-path", "actions": [{"condition": condition}]}],
    }
    gwcm = GenericWebhookConfigManifest(raw_config)
    action = gwcm.list_webhook_config[0].list_actions[0]
    result = action.condition.get_value(context)
    assert result == expected_result
