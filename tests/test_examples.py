import os

import pytest
import yaml

from generic_k8s_webhook.config_parser import GenericWebhookConfigManifest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXAMPLES_DIR = os.path.join(SCRIPT_DIR, "../examples")
LIST_EXAMPLE_FILES = [
    os.path.normpath(os.path.join(EXAMPLES_DIR, f)) for f in os.listdir(EXAMPLES_DIR) if f.endswith(".yaml")
]


@pytest.mark.parametrize("config_file", LIST_EXAMPLE_FILES)
def test_configs_in_examples_dir(config_file):
    with open(config_file, "r", encoding="utf-8") as f:
        raw_manifest = yaml.safe_load(f)
    GenericWebhookConfigManifest(raw_manifest)
