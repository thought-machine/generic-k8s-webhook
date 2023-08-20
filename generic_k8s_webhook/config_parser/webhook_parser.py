import abc

from generic_k8s_webhook import utils
from generic_k8s_webhook.config_parser.action_parser import IActionParser
from generic_k8s_webhook.webhook import Webhook


class IWebhookParser(abc.ABC):
    def __init__(self, action_parser: IActionParser) -> None:
        """Object used to parse a webhook spec.

        Args:
            action_parser (IActionParser): The parser used to parse the actions
            that the webhook contains.
        """
        self.action_parser = action_parser

    @abc.abstractmethod
    def parse(self, raw_config: dict, path_wh: str) -> Webhook:
        pass


class WebhookParserV1(IWebhookParser):
    """Class to parse the webhook spec V1. Example:

    ```yaml
    name: <name>
    path: /<path>
    actions:
        - <action>
        - <action>
        - ...
    ```
    """

    def parse(self, raw_config: dict, path_wh: str) -> Webhook:
        name = utils.must_pop(raw_config, "name", f"The webhook {path_wh} must have a name")
        path = utils.must_pop(raw_config, "path", f"The webhook {path_wh} must have a path")

        raw_list_action_configs = utils.must_pop(
            raw_config, "actions", f"The webhook {name} must have a actions defined"
        )
        list_actions = [
            self.action_parser.parse(raw_action, f"{path_wh}.actions.{i}")
            for i, raw_action in enumerate(raw_list_action_configs)
        ]

        if len(raw_config) > 0:
            raise ValueError(f"Invalid fields in webhook {path_wh}: {raw_config}")

        return Webhook(name, path, list_actions)
