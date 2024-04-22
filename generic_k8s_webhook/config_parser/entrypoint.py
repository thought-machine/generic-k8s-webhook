import copy

import generic_k8s_webhook.config_parser.operator_parser as op_parser
from generic_k8s_webhook import utils
from generic_k8s_webhook.config_parser import expr_parser
from generic_k8s_webhook.config_parser.action_parser import ActionParserV1
from generic_k8s_webhook.config_parser.jsonpatch_parser import JsonPatchParserV1
from generic_k8s_webhook.config_parser.webhook_parser import WebhookParserV1
from generic_k8s_webhook.webhook import Webhook


class GenericWebhookConfigManifest:
    EXPECTED_APIGROUP = "generic-webhook"
    EXPECTED_KIND = "GenericWebhookConfig"

    def __init__(self, raw_config: dict) -> None:
        """Parses a raw_config (the configuration of the webhook in yaml format) and
        generates objects that the core of the app can manage and understand.
        This object is smart enough to parse differently the raw_config according to
        the version specified in the `apiVersion` field.

        Example of raw_config:

        ```yaml
        apiVersion: generic-webhook/v1alpha1
        kind: GenericWebhookConfig
        webhooks:
            - <webhook>
            - <webhook>
            - ...
        ```

        Args:
            raw_config (dict): The configuration of the webhook extracted from the config
            yaml file.

        Raises:
            ValueError: if the `raw_config` is invalid
        """
        # We do a deep copy of raw_config since we remove its fields as we read them
        raw_config = copy.deepcopy(raw_config)

        raw_api_version = utils.must_pop(raw_config, "apiVersion", "apiVersion not defined")

        self.apigroup = raw_api_version.split("/")[0]
        if self.apigroup != self.EXPECTED_APIGROUP:
            raise ValueError(f"Invalid apigroup {self.apigroup}. Must be {self.EXPECTED_APIGROUP}")

        self.apiversion = raw_api_version.split("/")[1]

        self.kind = utils.must_pop(raw_config, "kind", "kind not defined")
        if self.kind != self.EXPECTED_KIND:
            raise ValueError(f"Invalid kind {self.kind}. Must be {self.EXPECTED_KIND}")

        raw_list_webhook_config = utils.must_pop(raw_config, "webhooks", "webhooks not defined")
        if not isinstance(raw_list_webhook_config, list):
            raise ValueError(f"The webhooks must be a list but it's a {type(raw_list_webhook_config)}")
        # Select the correct parsing method according to the api version, since different api versions
        # expect different schemas
        if self.apiversion == "v1alpha1":
            self.list_webhook_config = self._parse_v1alpha1(raw_list_webhook_config)
        elif self.apiversion == "v1beta1":
            self.list_webhook_config = self._parse_v1beta1(raw_list_webhook_config)
        else:
            raise ValueError(f"The api version {self.apiversion} is not supported")

        if len(raw_config) > 0:
            raise ValueError(f"Invalid fields at the manifest level: {raw_config}")

    def _parse_v1alpha1(self, raw_list_webhook_config: dict) -> list[Webhook]:
        webhook_parser = WebhookParserV1(
            action_parser=ActionParserV1(
                meta_op_parser=op_parser.MetaOperatorParser(
                    list_op_parser_classes=[
                        op_parser.AndParser,
                        op_parser.OrParser,
                        op_parser.EqualParser,
                        op_parser.SumParser,
                        op_parser.NotParser,
                        op_parser.ListParser,
                        op_parser.ForEachParser,
                        op_parser.ContainParser,
                        op_parser.ConstParser,
                        op_parser.GetValueParser,
                    ],
                    raw_str_parser=expr_parser.RawStringParserNotImplemented(),
                ),
                json_patch_parser=JsonPatchParserV1(),
            )
        )
        list_webhook_config = [
            webhook_parser.parse(raw_webhook_config, f"webhooks.{i}")
            for i, raw_webhook_config in enumerate(raw_list_webhook_config)
        ]
        return list_webhook_config

    def _parse_v1beta1(self, raw_list_webhook_config: dict) -> list[Webhook]:
        webhook_parser = WebhookParserV1(
            action_parser=ActionParserV1(
                meta_op_parser=op_parser.MetaOperatorParser(
                    list_op_parser_classes=[
                        op_parser.AndParser,
                        op_parser.AllParser,
                        op_parser.OrParser,
                        op_parser.AnyParser,
                        op_parser.EqualParser,
                        op_parser.SumParser,
                        op_parser.NotParser,
                        op_parser.ListParser,
                        op_parser.ForEachParser,
                        op_parser.MapParser,
                        op_parser.ContainParser,
                        op_parser.ConstParser,
                        op_parser.GetValueParser,
                    ],
                    raw_str_parser=expr_parser.RawStringParserV1(),
                ),
                json_patch_parser=JsonPatchParserV1(),
            )
        )
        list_webhook_config = [
            webhook_parser.parse(raw_webhook_config, f"webhooks.{i}")
            for i, raw_webhook_config in enumerate(raw_list_webhook_config)
        ]
        return list_webhook_config
