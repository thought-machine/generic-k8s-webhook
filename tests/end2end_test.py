import base64
import json
import os
import signal
import subprocess
import threading

import pytest
import requests
import yaml
from http_server_test import get_free_port, load_test_case, wait_for_server_ready

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HTTP_SERVER_TEST_DATA_DIR = os.path.join(SCRIPT_DIR, "http_server_test_data")
TLS_DIR = os.path.join(SCRIPT_DIR, "tls")
CERT_FILE = os.path.join(TLS_DIR, "cert.pem")
KEY_FILE = os.path.join(TLS_DIR, "key.pem")
MAIN_PY = os.path.join(SCRIPT_DIR, "../generic_k8s_webhook/main.py")


class ServerShell:
    def __init__(self, webhook_config_file: str, port: int, tls: bool) -> None:
        tls_args = ""
        if tls:
            tls_args = f"--cert-file {CERT_FILE} --key-file {KEY_FILE}"
        self.cmd = f"poetry run python3 {MAIN_PY} --config {webhook_config_file} server --port {port} {tls_args}"
        self.process: subprocess.Popen

    def start(self):
        self.process = subprocess.Popen(self.cmd, shell=True)

    def stop(self):
        self.process.send_signal(signal.SIGTERM)

    def wait_to_finish(self):
        self.process.communicate()


@pytest.mark.parametrize(
    ("name_test", "req", "webhook_config", "expected_response"),
    load_test_case(os.path.join(HTTP_SERVER_TEST_DATA_DIR, "test_case_1.yaml"))
    + load_test_case(os.path.join(HTTP_SERVER_TEST_DATA_DIR, "test_case_3.yaml")),
)
@pytest.mark.parametrize("tls", [False, True])
def test_http_server_e2e(name_test, req, webhook_config, expected_response, tls, tmp_path):
    webhook_config_file = tmp_path / "webhook_config.yaml"
    with open(webhook_config_file, "w") as f:
        yaml.safe_dump(webhook_config, f)

    port = get_free_port()
    server_shell = ServerShell(webhook_config_file, port, tls)
    t = threading.Thread(target=server_shell.start)
    t.start()
    wait_for_server_ready(port, tls=tls)

    if tls:
        url = f"https://localhost:{port}{req['path']}"
    else:
        url = f"http://localhost:{port}{req['path']}"

    response = requests.post(url, json=req["body"], verify=False, timeout=1)
    json_response = json.loads(response.content.decode("utf-8"))
    # If we have a "patch" field in the response, convert it from a base64 encoded string to a dict
    if "patch" in json_response["response"]:
        json_response["response"]["patch"] = json.loads(base64.b64decode(json_response["response"]["patch"]))

    assert json_response == expected_response

    server_shell.stop()
    server_shell.wait_to_finish()
    t.join()


def test_cli_program_version():
    cmd = f"poetry run python3 {MAIN_PY} --version"
    subprocess.run(cmd, shell=True, check=True)


def test_cli_help():
    cmd = f"poetry run python3 {MAIN_PY} --help"
    subprocess.run(cmd, shell=True, check=True)
