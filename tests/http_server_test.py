import base64
import json
import os
import threading
import time

import pytest
import requests
import yaml
from test_utils import get_free_port, load_test_case, wait_for_server_ready

from generic_k8s_webhook.http_server import Server

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HTTP_SERVER_TEST_DATA_DIR = os.path.join(SCRIPT_DIR, "http_server_test_data")


@pytest.mark.parametrize(
    ("name_test", "req", "webhook_config", "expected_response"),
    load_test_case(os.path.join(HTTP_SERVER_TEST_DATA_DIR, "test_case_1.yaml"))
    + load_test_case(os.path.join(HTTP_SERVER_TEST_DATA_DIR, "test_case_3.yaml"))
    + load_test_case(os.path.join(HTTP_SERVER_TEST_DATA_DIR, "test_case_4.yaml")),
)
def test_http_server(name_test, req, webhook_config, expected_response, tmp_path):
    webhook_config_file = tmp_path / "webhook_config.yaml"
    with open(webhook_config_file, "w") as f:
        yaml.safe_dump(webhook_config, f)

    port = get_free_port()
    server = Server(port, "", "", webhook_config_file)
    t = threading.Thread(target=server.start)
    t.start()
    wait_for_server_ready(port)

    # Check the server behaves correctly when we send (or not) http parameters
    for url_params in ["", "?param1=value1"]:
        url = f"http://localhost:{port}{req['path']}{url_params}"
        response = requests.post(url, json=req["body"], timeout=1)
        assert response.status_code == 200, f"Status code {response.status_code} when doing POST to {url}"

        json_response = json.loads(response.content.decode("utf-8"))
        # If we have a "patch" field in the response, convert it from a base64 encoded string to a dict
        if "patch" in json_response["response"]:
            json_response["response"]["patch"] = json.loads(base64.b64decode(json_response["response"]["patch"]))

        assert json_response == expected_response

    server.stop()
    t.join()


def test_auto_reload(tmp_path):
    list_cases = load_test_case(os.path.join(HTTP_SERVER_TEST_DATA_DIR, "test_case_1.yaml"))
    webhook_config_file = tmp_path / "webhook_config.yaml"
    config_refresh_period = 1

    _, _, webhook_config, _ = list_cases[0]
    with open(webhook_config_file, "w") as f:
        yaml.safe_dump(webhook_config, f)

    port = get_free_port()
    server = Server(port, "", "", webhook_config_file, config_refresh_period)
    t = threading.Thread(target=server.start)
    t.start()
    wait_for_server_ready(port)

    for _, req, webhook_config, expected_response in list_cases:
        with open(webhook_config_file, "w") as f:
            yaml.safe_dump(webhook_config, f)

        # Wait for the auto-reload process of the configuration
        time.sleep(config_refresh_period * 1.5)

        url = f"http://localhost:{port}{req['path']}"
        response = requests.post(url, json=req["body"], timeout=1)
        json_response = json.loads(response.content.decode("utf-8"))

        assert json_response == expected_response

    server.stop()
    t.join()


def test_two_webhooks_same_server(tmp_path):
    list_cases = load_test_case(os.path.join(HTTP_SERVER_TEST_DATA_DIR, "test_case_2.yaml"))
    webhook_config_file = tmp_path / "webhook_config.yaml"
    config_refresh_period = 1

    _, _, webhook_config, _ = list_cases[0]
    with open(webhook_config_file, "w") as f:
        yaml.safe_dump(webhook_config, f)

    port = get_free_port()
    server = Server(port, "", "", webhook_config_file, config_refresh_period)
    t = threading.Thread(target=server.start)
    t.start()
    wait_for_server_ready(port)

    # In this test, we can ignore the webhook_config, since it's the same in all the cases
    for _, req, _, expected_response in list_cases:
        url = f"http://localhost:{port}{req['path']}"
        response = requests.post(url, json=req["body"], timeout=1)
        json_response = json.loads(response.content.decode("utf-8"))

        assert json_response == expected_response

    server.stop()
    t.join()
