import base64
import http.server
import json
import logging
import ssl
import threading
from urllib.parse import urlparse

import jsonpatch
import yaml

from generic_k8s_webhook.config_parser.entrypoint import GenericWebhookConfigManifest
from generic_k8s_webhook.webhook import Webhook


class ConfigLoader(threading.Thread):
    def __init__(self, generic_webhook_config_file: str, refresh_period: float) -> None:
        """A class to reload a webhook configuration in a separate thread

        Args:
            generic_webhook_config_file (str): The file that contains the
            configuration of the webhook
            refresh_period (float): The time it waits to refresh again the
            configuration
        """
        super().__init__()
        self.generic_webhook_config_file = generic_webhook_config_file
        self.refresh_period = refresh_period
        self.manifest: GenericWebhookConfigManifest | None = None
        self.lock = threading.Lock()
        self._reload_manifest()
        self.stop_flag = False
        self.cond = threading.Condition()
        self.stop_event = threading.Event()

    def _reload_manifest(self) -> None:
        with open(self.generic_webhook_config_file, "r", encoding="utf-8") as f:
            raw_manifest = yaml.safe_load(f)
        with self.lock:
            self.manifest = GenericWebhookConfigManifest(raw_manifest)

    def run(self) -> None:
        while not self.stop_event.wait(self.refresh_period):
            try:
                self._reload_manifest()
            except Exception as e:  # pylint: disable=broad-exception-caught
                logging.error(e, exc_info=True)

    def get_webhooks(self) -> list[Webhook]:
        with self.lock:
            return self.manifest.list_webhook_config

    def stop(self) -> None:
        self.stop_event.set()


class BaseHandler(http.server.BaseHTTPRequestHandler):
    CONFIG_LOADER: ConfigLoader | None = None
    HEALTHZ = "/healthz"

    def do_GET(self):
        try:
            self._do_get()
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging.error(e, exc_info=True)

    def _do_get(self):
        if self._get_path() == self.HEALTHZ:
            self._healthz()
        else:
            self.send_response(400)
            self.end_headers()

    def do_POST(self):
        try:
            self._do_post()
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging.error(e, exc_info=True)

    def _do_post(self):
        logging.info(f"Processing request from {self.address_string()}")
        webhook_paths = [webhook.path for webhook in self.CONFIG_LOADER.get_webhooks()]

        # The path in the url is not defined in this server
        if self._get_path() not in webhook_paths:
            self.send_response(400)
            self.end_headers()
            logging.error(f"Wrong path {self.path} Not defined")
            return

        request = self._get_body_request()
        uid = request["uid"]
        # Calling in order all the webhooks that have the target path. They all must set accept=True to
        # accept the request. The patches are concatenated and applied for the next call to "process_manifest"
        final_patch = jsonpatch.JsonPatch([])
        for webhook in self.CONFIG_LOADER.get_webhooks():
            if self._get_path() == webhook.path:
                # The call to the current webhook needs a json object that has been updated by the previous patches
                patched_object = final_patch.apply(request["object"])
                accept, patch = webhook.process_manifest(patched_object)
                final_patch = jsonpatch.JsonPatch(list(final_patch) + list(patch))
                if not accept:
                    break

        response = self._generate_response(uid, accept, final_patch)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(response).encode("utf-8"))

    def _generate_response(self, uid: str, accept: bool, patch: jsonpatch.JsonPatch) -> dict:
        response = {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": {"uid": uid, "allowed": accept},
        }
        if patch:
            response["response"]["patchType"] = "JSONPatch"
            response["response"]["patch"] = base64.b64encode(patch.to_string().encode("utf-8")).decode("utf-8")
        return response

    def _healthz(self) -> None:
        self.send_response(200)
        self.end_headers()
        self.wfile.write("I'm alive\n".encode("utf-8"))

    def _get_path(self) -> str:
        parsed_url = urlparse(self.path)
        return parsed_url.path

    def _get_body_request(self) -> dict:
        """Returns the "request" field of the body of the current request"""
        content_length = int(self.headers["Content-Length"])
        raw_body = self.rfile.read(content_length)
        body = json.loads(raw_body)
        request = body["request"]
        return request


class Server:
    def __init__(  # pylint: disable=too-many-arguments
        self, port: int, certfile: str, keyfile: str, generic_webhook_config_file: str, config_refresh_period: float = 5
    ) -> None:
        """Validating/Mutating webhook server. It listens to requests made at port <port>
        and sends the corresponding answer according to the configuration from
        <generic_webhook_config_file>

        Args:
            port (int): Port where the server listens to

            certfile (str): Certifica file for the TLS connection. If not provided,
            the server will be http, not https

            keyfile (str): Key file for the TLS connection. If not provided,
            the server will be http, not https

            generic_webhook_config_file (str): File that contains the configuration for
            the webhooks that this server must implement

            config_refresh_period (float, optional): This is the time, in seconds,
            that the system waits before reading again the webhook config file.
            This enables changing the configuration without restarting the server.
            Defaults to 5.
        """
        self.port = port
        self.config_loader = ConfigLoader(generic_webhook_config_file, config_refresh_period)

        # The Handler is created and destroyed for each request processed
        class Handler(BaseHandler):
            CONFIG_LOADER = self.config_loader

        self.httpd = http.server.HTTPServer(("0.0.0.0", self.port), Handler)
        if certfile and keyfile:
            context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
            context.load_cert_chain(certfile, keyfile)
            self.httpd.socket = context.wrap_socket(self.httpd.socket, server_side=True)

    def start(self) -> None:
        logging.info(f"Starting server that listens of port {self.port}")
        self.config_loader.start()
        self.httpd.serve_forever()
        logging.info("Closing server...")
        self.httpd.server_close()
        self.config_loader.join()
        logging.info("Server stopped")

    def stop(self) -> None:
        logging.info("The server must stop")
        self.config_loader.stop()
        self.httpd.shutdown()
        logging.info("Shutdown completed")
