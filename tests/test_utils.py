import copy
import os
import socket
from typing import Any
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
