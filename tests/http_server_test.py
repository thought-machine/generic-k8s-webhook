import base64
import copy
import yaml
import pytest
from pathlib import Path
from typing import Any
import os
import socket
import threading
import requests
import json
import time

from generic_k8s_webhook.http_server import Server

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HTTP_SERVER_TEST_DATA_DIR = os.path.join(SCRIPT_DIR, "http_server_test_data")


def patch_dict(d: dict, key: list, value: Any) -> None:
    if len(key) < 1:
        raise RuntimeError("No element in key")
    elif len(key) == 1:
        d[key[0]] = value
    else:
        patch_dict(d[key[0]], key[1:], value)


def load_test_case(yaml_file: str) -> list[tuple]:
    with open(yaml_file, "r") as f:
        raw_test_case = yaml.safe_load(f)

    list_cases = []
    for i, case in enumerate(raw_test_case["cases"]):
        all_config = copy.deepcopy(raw_test_case)
        for patch in case["patches"]:
            patch_dict(all_config, patch["key"], patch["value"])
        request = all_config["request"]
        webhook_config = all_config["webhook_config"]
        name_test = f"{os.path.basename(yaml_file)}-case-{i}"
        list_cases.append((name_test, request, webhook_config, case["expected_response"]))

    return list_cases


def get_free_port() -> int:
    sock = socket.socket()
    sock.bind(('', 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.mark.parametrize(("name_test", "req", "webhook_config", "expected_response"),
                         load_test_case(os.path.join(HTTP_SERVER_TEST_DATA_DIR, "test_case_1.yaml"))
                         + load_test_case(os.path.join(HTTP_SERVER_TEST_DATA_DIR, "test_case_3.yaml")))
def test_http_server(name_test, req, webhook_config, expected_response, tmp_path):
    webhook_config_file = tmp_path / "webhook_config.yaml"
    with open(webhook_config_file, "w") as f:
        yaml.safe_dump(webhook_config, f)

    port = get_free_port()
    server = Server(port, webhook_config_file)
    t = threading.Thread(target=server.start)
    t.start()

    url = f"http://localhost:{port}{req['path']}"
    response = requests.post(url, json=req["body"])
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
    server = Server(port, webhook_config_file, config_refresh_period)
    t = threading.Thread(target=server.start)
    t.start()

    for _, req, webhook_config, expected_response in list_cases:
        with open(webhook_config_file, "w") as f:
            yaml.safe_dump(webhook_config, f)

        # Wait for the auto-reload process of the configuration
        time.sleep(config_refresh_period * 1.5)

        url = f"http://localhost:{port}{req['path']}"
        response = requests.post(url, json=req["body"])
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
    server = Server(port, webhook_config_file, config_refresh_period)
    t = threading.Thread(target=server.start)
    t.start()

    # In this test, we can ignore the webhook_config, since it's the same in all the cases
    for _, req, _, expected_response in list_cases:
        url = f"http://localhost:{port}{req['path']}"
        response = requests.post(url, json=req["body"])
        json_response = json.loads(response.content.decode("utf-8"))

        assert json_response == expected_response

    server.stop()
    t.join()
