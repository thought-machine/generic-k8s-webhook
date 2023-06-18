import pytest
import yaml
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR + "/..")

import generic_k8s_webhook.config_parser as config_parser


def get_yaml(path: str) -> dict:
    abs_path = os.path.join(SCRIPT_DIR, path)
    with open(abs_path, "r") as f:
        return yaml.safe_load(f)


def test_valid_config():
    raw_config = get_yaml("webhook_configs/config1.yaml")
    config = config_parser.Manifest(raw_config)
    assert config.apigroup == "generic-webhook"
    assert config.apiversion == "v1alpha1"
    assert config.kind == raw_config["kind"]
    assert len(config.list_webhook_config) == 1

    webhook = config.list_webhook_config[0]
    raw_webhook = raw_config["webhooks"][0]
    assert webhook.name == raw_webhook["name"]
    assert webhook.path == raw_webhook["path"]
    assert len(webhook.list_actions) == 1

    action = webhook.list_actions[0]
    assert action.accept == True
