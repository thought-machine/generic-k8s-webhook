import argparse
import json
import logging
import signal
import sys
import threading

import yaml

from generic_k8s_webhook import __version__
from generic_k8s_webhook.config_parser import GenericWebhookConfigManifest
from generic_k8s_webhook.http_server import Server


def cli(args):
    with open(args.config, "r", encoding="utf-8") as f:
        raw_config = yaml.safe_load(f)
    with open(args.k8s_manifest, "r", encoding="utf-8") as f:
        k8s_manifest = yaml.safe_load(f)

    config = GenericWebhookConfigManifest(raw_config)
    for webhook in config.list_webhook_config:
        if webhook.name == args.wh_name:
            accept, patch = webhook.process_manifest(k8s_manifest)
            if not accept:
                sys.exit(1)
            # Show the patch if it's not None
            if patch:
                if args.show_patch:
                    print(json.dumps(patch.patch, indent=2))
                else:
                    print(yaml.dump(patch.apply(k8s_manifest), indent=2))
            sys.exit(0)
    logging.error(
        f"Couldn't find a webhook called {args.wh_name}. "
        + f"Valid webhook names are {[webhook.name for webhook in config.list_webhook_config]}"
    )
    sys.exit(1)


def start_server(args):
    server = Server(args.port, args.cert_file, args.key_file, args.config)

    def stop_server(*args):
        threading.Thread(target=server.stop).start()

    signal.signal(signal.SIGINT, stop_server)
    signal.signal(signal.SIGTERM, stop_server)

    server.start()


def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Program to validate and/or modify K8S manifests")
    subparser = parser.add_subparsers(help="Program mode")

    parser.add_argument("--version", action="version", version=f"{__version__}")
    parser.add_argument("--config", type=str, required=True, help="GenericWebhookConfig config file")
    parser.add_argument("--verbose", "-v", action="count", default=0)

    server_subparser = subparser.add_parser("server", help="Create an http server")
    server_subparser.add_argument("--port", type=int, required=True, help="Port where the server will listen")
    server_subparser.add_argument(
        "--cert-file",
        type=str,
        help="Certificate file for the TLS connection. If not provided, the server will be a standard http one",
    )
    server_subparser.add_argument(
        "--key-file",
        type=str,
        help="Private key file for the TLS connection. If not provided, the server will be a standard http one",
    )
    server_subparser.set_defaults(func=start_server)

    cli_subparser = subparser.add_parser("cli", help="Use the program as a cli utility")
    cli_subparser.add_argument(
        "--k8s-manifest", type=str, required=True, help="K8S manifest file that the webhook will process"
    )
    cli_subparser.add_argument(
        "--wh-name",
        type=str,
        required=True,
        help="The name of the webhook that will be used to process the k8s manifest",
    )
    cli_subparser.add_argument(
        "--show-patch",
        action="store_true",
        help="When set, instead of showing the resulting manifest, it shows the patch that will be applied",
    )
    cli_subparser.set_defaults(func=cli)

    args = parser.parse_args()
    return args


def main():
    args = parse_args()
    logging.basicConfig(format="%(asctime)s,%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s")
    if args.verbose > 0:
        logging.basicConfig(
            format="%(asctime)s,%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s", level=logging.INFO
        )
    args.func(args)


if __name__ == "__main__":
    main()
