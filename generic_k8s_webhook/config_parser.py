import abc
import copy
import inspect
import re
import sys

import generic_k8s_webhook.utils as utils
import generic_k8s_webhook.operators as operators
from generic_k8s_webhook.webhook import Webhook, Action


class ParsingException(Exception):
    pass

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
        self.list_webhook_config = [WebhookParser.parse(raw_webhook_config, f"webhooks.{i}")
                                    for i, raw_webhook_config in enumerate(raw_list_webhook_config)]

        if len(raw_config) > 0:
            ValueError(f"Invalid fields at the manifest level: {raw_config}")


class WebhookParser:
    @classmethod
    def parse(clx, raw_config: dict, path_wh: str) -> Webhook:
        name = utils.must_pop(raw_config, "name", f"The webhook {path_wh} must have a name")
        path = utils.must_pop(raw_config, "path", f"The webhook {path_wh} must have a path")

        raw_list_action_configs = utils.must_pop(raw_config, "actions",
                                                 f"The webhook {name} must have a actions defined")
        list_actions = [ActionParser.parse(raw_action, f"{path_wh}.actions.{i}")
                        for i, raw_action in enumerate(raw_list_action_configs)]

        if len(raw_config) > 0:
            ValueError(f"Invalid fields in webhook {path_wh}: {raw_config}")

        return Webhook(name, path, list_actions)


class ActionParser:
    @classmethod
    def parse(cls, raw_config: dict, path_action: str) -> Action:
        # TODO Add support for the "forEach" keyword
        #
        # raw_foreach = raw_config.pop("forEach", None)
        # if raw_foreach is not None:
        #     self.foreach  = operators.parse_operator(raw_foreach, "forEach")
        # else:
        #     self.foreach = None

        # If the condition is not defined, we default to True
        raw_condition = raw_config.pop("condition", {"const": True})
        condition = parse_operator(raw_condition, f"{path_action}.condition")

        patch = raw_config.pop("patch", None)
        # By default, we always accept the payload
        accept = raw_config.pop("accept", True)

        if len(raw_config) > 0:
            ValueError(f"Invalid fields in action {path_action}: {raw_config}")

        return Action(condition, patch, accept)


class OperatorParser(abc.ABC):
    @abc.abstractclassmethod
    def parse(cls, op_inputs: dict | list, path_op: str) -> operators.Operator:
        pass


class BinaryOpParser(OperatorParser):
    OPERATOR_CLS = operators.BinaryOp

    @classmethod
    def parse(cls, op_inputs: dict | list, path_op: str) -> operators.BinaryOp:
        if isinstance(op_inputs, list):
            args = ListParser.parse(op_inputs, path_op)
        elif isinstance(op_inputs, dict):
            args = parse_operator(op_inputs, path_op)
        else:
            raise ValueError(f"Expected dict or list as input, but got {op_inputs}")

        try:
            return cls.OPERATOR_CLS(args)
        except TypeError as e:
            raise ParsingException(f"Error when parsing {path_op}. {e}")


class AndParser(BinaryOpParser):
    NAME = "and"
    OPERATOR_CLS = operators.And


class OrParser(BinaryOpParser):
    NAME = "or"
    OPERATOR_CLS = operators.Or


class EqualParser(BinaryOpParser):
    NAME = "equal"
    OPERATOR_CLS = operators.Equal


class SumParser(BinaryOpParser):
    NAME = "sum"
    OPERATOR_CLS = operators.Sum


class UnaryOpParser(OperatorParser):
    OPERATOR_CLS = operators.UnaryOp

    @classmethod
    def parse(cls, op_inputs: dict | list, path_op: str) -> operators.UnaryOp:
        arg = parse_operator(op_inputs, path_op)
        try:
            return cls.OPERATOR_CLS(arg)
        except TypeError as e:
            raise ParsingException(f"Error when parsing {path_op}. {e}")


class NotParser(UnaryOpParser):
    NAME = "not"
    OPERATOR_CLS = operators.Not

class ListParser(OperatorParser):
    NAME = "list"

    @classmethod
    def parse(cls, op_inputs: dict | list, path_op: str) -> operators.List:
        list_op = []
        for i, op in enumerate(op_inputs):
            parsed_op = parse_operator(op, f"{path_op}.{i}")
            list_op.append(parsed_op)
        try:
            return operators.List(list_op)
        except TypeError as e:
            raise ParsingException(f"Error when parsing {path_op}. {e}")


class ForEachParser(OperatorParser):
    NAME = "forEach"

    @classmethod
    def parse(cls, op_inputs: dict | list, path_op: str) -> operators.ForEach:
        raw_elements = utils.must_get(op_inputs, "elements", f"In {path_op}, required 'elements'")
        elements = parse_operator(raw_elements, f"{path_op}.elements")

        raw_op = utils.must_get(op_inputs, "op", f"In {path_op}, required 'op'")
        op = parse_operator(raw_op, f"{path_op}.op")

        try:
            return operators.ForEach(elements, op)
        except TypeError as e:
            raise ParsingException(f"Error when parsing {path_op}. {e}")


class ContainParser(OperatorParser):
    NAME = "contain"

    @classmethod
    def parse(cls, op_inputs: dict | list, path_op: str) -> operators.Contain:
        raw_elements = utils.must_get(op_inputs, "elements", f"In {path_op}, required 'elements'")
        elements = parse_operator(raw_elements, f"{path_op}.elements")

        raw_elem = utils.must_get(op_inputs, "value", f"In {path_op}, required 'value'")
        elem = parse_operator(raw_elem, f"{path_op}.value")

        try:
            return operators.Contain(elements, elem)
        except TypeError as e:
            raise ParsingException(f"Error when parsing {path_op}. {e}")


class ConstParser(OperatorParser):
    NAME = "const"

    @classmethod
    def parse(cls, op_inputs: dict | list, path_op: str) -> operators.Const:
        try:
            return operators.Const(op_inputs)
        except TypeError as e:
            raise ParsingException(f"Error when parsing {path_op}. {e}")


class GetValueParser(OperatorParser):
    NAME = "getValue"

    @classmethod
    def parse(cls, op_inputs: dict | list, path_op: str) -> operators.GetValue:
        if not isinstance(op_inputs, str):
            raise ValueError(f"Expected to find str but got {op_inputs} in {path_op}")
        # Split by '.', but not by '\.'
        path = re.split(r"(?<!\\)\.", op_inputs)
        # Convert the '\.' to '.'
        path = [elem.replace("\\.", ".") for elem in path]

        # Get the id of the context that it will use
        if path[0] == "":
            context_id = -1
        elif path[0] == "$":
            context_id = 0
        else:
            raise ValueError(f"Invalid {path[0]} in {path_op}")

        try:
            return operators.GetValue(path, context_id)
        except TypeError as e:
            raise ParsingException(f"Error when parsing {path_op}. {e}")


# Magic dictionary that contains all the operators config defined in this file
DICT_OPERATORS = {}
for _, obj in inspect.getmembers(sys.modules[__name__]):
    if (isinstance(obj, type) and
        issubclass(obj, OperatorParser) and
        hasattr(obj, "NAME")):
            if obj.NAME in DICT_OPERATORS:
                raise RuntimeError(f"Duplicated operator {obj.NAME}")
            DICT_OPERATORS[obj.NAME] = obj


def parse_operator(op_spec: dict, path_op: str="") -> operators.Operator:
    if len(op_spec) != 1:
        raise ValueError(f"Expected exactly one key under {path_op}")
    op_name, op_spec = op_spec.popitem()
    if op_name not in DICT_OPERATORS:
        raise ValueError(f"The operator {op_name} from {path_op} is not defined")
    op_class = DICT_OPERATORS[op_name]
    op = op_class.parse(op_spec, f"{path_op}.{op_name}")

    return op
