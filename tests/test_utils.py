import copy
import os
import socket
import time
from typing import Any

import requests
import yaml


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
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def wait_for_server_ready(port: int, tls: bool = False) -> None:
    if tls:
        url = f"https://localhost:{port}/healthz"
    else:
        url = f"http://localhost:{port}/healthz"
    for _ in range(20):
        try:
            response = requests.get(url, verify=False, timeout=1)
            if response.status_code == 200:
                break
        except:
            pass
        time.sleep(0.1)
    response = requests.get(url, verify=False, timeout=1)
    if response.status_code != 200:
        raise RuntimeError(f"Error when doing the health check to the server. Error {response.status_code}")
