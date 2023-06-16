import copy
import generic_k8s_webhook.utils as utils
import generic_k8s_webhook.operators as operators


class Manifest:
    APIGROUP = "generic-webhook"
    KIND = "GenericWebhookConfig"

    def __init__(self, raw_config: dict) -> None:
        # We do a deep copy of raw_config since we remove its fields as we read them
        raw_config = copy.deepcopy(raw_config)
        
        raw_api_version = utils.must_pop(raw_config, "apiVersion", "apiVersion not defined")

        self.apigroup = raw_api_version.split("/")[0]
        if self.apigroup != self.APIGROUP:
            raise ValueError(f"Invalid apigroup {self.apigroup}. Must be {self.APIGROUP}")

        self.apiversion = raw_api_version.split("/")[1]

        self.kind = utils.must_pop(raw_config, "kind", "kind not defined")
        if self.kind != self.KIND:
            raise ValueError(f"Invalid kind {self.kind}. Must be {self.KIND}")

        raw_list_webhook_config = utils.must_pop(raw_config, "webhooks", "webhooks not defined")
        if not isinstance(raw_list_webhook_config, list):
            raise ValueError(f"The webhooks must be a list but it's a {type(raw_list_webhook_config)}")
        self.list_webhook_config = [WebhookConfig(raw_webhook_config) for raw_webhook_config in raw_list_webhook_config]

        if len(raw_config) > 0:
            ValueError(f"Invalid fields at the manifest level: {raw_config}")


class WebhookConfig:
    def __init__(self, raw_config: dict) -> None:
        self.name = utils.must_pop(raw_config, "name", "The webhook must have a name")
        self.port = utils.must_pop(raw_config, "port", f"The webhook {self.name} must have a port")
        self.path = utils.must_pop(raw_config, "path", f"The webhook {self.name} must have a path")

        raw_list_actions = utils.must_pop(raw_config, "actions", f"The webhook {self.name} must have a actions defined")
        self.actions = [Action(raw_action) for raw_action in raw_list_actions]

        if len(raw_config) > 0:
            ValueError(f"Invalid fields in webhook {self.name}: {raw_config}")


class Action:
    def __init__(self, raw_config: dict) -> None:
        self.for_each = raw_config.pop("forEach", None)

        # If the condition is not defined, we default to True
        raw_condition = raw_config.pop("condition", {"const": True})
        self.condition = operators.parse_operator(raw_condition, "condition")

        self.patch = raw_config.pop("patch", None)
        # By default, we always accept the payload
        self.accept = raw_config.pop("accept", True)

        if len(raw_config) > 0:
            ValueError(f"Invalid fields in an action: {raw_config}")
