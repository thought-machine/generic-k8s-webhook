import abc

from generic_k8s_webhook.config_parser.jsonpatch_parser import IJsonPatchParser
from generic_k8s_webhook.config_parser.operator_parser import MetaOperatorParser
from generic_k8s_webhook.webhook import Action


class IActionParser(abc.ABC):
    def __init__(self, meta_op_parser: MetaOperatorParser, json_patch_parser: IJsonPatchParser) -> None:
        """Object used to parse an action spec.

        Args:
            meta_op_parser (MetaOperatorParser): The parser used to parse the operators that define the condition
            json_patch_parser (IJsonPatchParser): The parser used to parse the patch
        """
        self.meta_op_parser = meta_op_parser
        self.json_patch_parser = json_patch_parser

    @abc.abstractmethod
    def parse(self, raw_config: dict, path_action: str) -> Action:
        pass


class ActionParserV1(IActionParser):
    """Class used to parse an action spec V1. Example:

    ```yaml
    condition: <operator>
    accept: <true|false>
    patch: <patch>
    ```
    """

    def parse(self, raw_config: dict, path_action: str) -> Action:
        # TODO Add support for the "forEach" keyword
        #
        # raw_foreach = raw_config.pop("forEach", None)
        # if raw_foreach is not None:
        #     self.foreach  = operators.parse_operator(raw_foreach, "forEach")
        # else:
        #     self.foreach = None

        # If the condition is not defined, we default to True
        raw_condition = raw_config.pop("condition", {"const": True})
        condition = self.meta_op_parser.parse(raw_condition, f"{path_action}.condition")

        raw_patch = raw_config.pop("patch", [])
        patch = self.json_patch_parser.parse(raw_patch)

        # By default, we always accept the payload
        accept = raw_config.pop("accept", True)

        if len(raw_config) > 0:
            raise ValueError(f"Invalid fields in action {path_action}: {raw_config}")

        return Action(condition, patch, accept)
