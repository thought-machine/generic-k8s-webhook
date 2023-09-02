import abc
import inspect

import generic_k8s_webhook.config_parser.expr_parser as expr_parser
from generic_k8s_webhook import operators, utils
from generic_k8s_webhook.config_parser.common import ParsingException


class MetaOperatorParser:
    def __init__(self, list_op_parser_classes: list[type], raw_str_parser: expr_parser.IRawStringParser) -> None:
        self.dict_op_parser = {}
        for op_parser_class in list_op_parser_classes:
            # Make sure that op_parser_class is a proper "OperatorParser" derived class
            if (
                not isinstance(op_parser_class, type)
                or not issubclass(op_parser_class, OperatorParser)
                or inspect.isabstract(op_parser_class)
            ):
                raise RuntimeError(f"Invalid op class {op_parser_class}")
            # Generate an instance that will parse a specific operator and safe it to a dict
            op_parser = op_parser_class(self)
            if op_parser.get_name() in self.dict_op_parser:
                raise RuntimeError(f"Duplicated operator parser {op_parser.get_name()}")
            self.dict_op_parser[op_parser.get_name()] = op_parser

        self.raw_str_parser = raw_str_parser

    def parse(self, op_spec: dict | str, path_op: str) -> operators.Operator:
        if isinstance(op_spec, dict):
            return self._parse_dict(op_spec, path_op)
        if isinstance(op_spec, str):
            return self._parse_str(op_spec, path_op)
        raise RuntimeError(f"Cannot parse the type {type(op_spec)}. It must be dict or str")

    def _parse_dict(self, op_spec: dict, path_op: str) -> operators.Operator:
        """It's used to parse a structured operator. Example:

        ```yaml
        sum:
            - const: 4
            - const: 5
        ```
        """
        if len(op_spec) != 1:
            raise ValueError(f"Expected exactly one key under {path_op}")
        op_name, op_spec = op_spec.popitem()
        if op_name not in self.dict_op_parser:
            raise ValueError(f"The operator {op_name} from {path_op} is not defined")
        op_parser = self.dict_op_parser[op_name]
        op = op_parser.parse(op_spec, f"{path_op}.{op_name}")

        return op

    def _parse_str(self, op_spec: str, path_op: str) -> operators.Operator:
        """It's used to parse an unstructured operator. Example:

        ```yaml
        "4 + 5"
        ```
        """
        try:
            return self.raw_str_parser.parse(op_spec)
        except Exception as e:
            raise ParsingException(f"Error when parsing {path_op}") from e


class OperatorParser(abc.ABC):
    def __init__(self, meta_op_parser: MetaOperatorParser) -> None:
        self.meta_op_parser = meta_op_parser

    @abc.abstractmethod
    def parse(self, op_inputs: dict | list, path_op: str) -> operators.Operator:
        pass

    @classmethod
    @abc.abstractmethod
    def get_name(cls) -> str:
        pass


class BinaryOpParser(OperatorParser):
    def parse(self, op_inputs: dict | list, path_op: str) -> operators.BinaryOp:
        if isinstance(op_inputs, list):
            list_parser = ListParser(self.meta_op_parser)
            args = list_parser.parse(op_inputs, path_op)
        elif isinstance(op_inputs, dict):
            args = self.meta_op_parser.parse(op_inputs, path_op)
        else:
            raise ValueError(f"Expected dict or list as input, but got {op_inputs}")

        try:
            return self.get_operator_cls()(args)
        except TypeError as e:
            raise ParsingException(f"Error when parsing {path_op}") from e

    @classmethod
    @abc.abstractmethod
    def get_operator_cls(cls) -> operators.BinaryOp:
        pass


class AndParser(BinaryOpParser):
    @classmethod
    def get_name(cls) -> str:
        return "and"

    @classmethod
    def get_operator_cls(cls) -> operators.BinaryOp:
        return operators.And


class OrParser(BinaryOpParser):
    @classmethod
    def get_name(cls) -> str:
        return "or"

    @classmethod
    def get_operator_cls(cls) -> operators.BinaryOp:
        return operators.Or


class EqualParser(BinaryOpParser):
    @classmethod
    def get_name(cls) -> str:
        return "equal"

    @classmethod
    def get_operator_cls(cls) -> operators.BinaryOp:
        return operators.Equal


class SumParser(BinaryOpParser):
    @classmethod
    def get_name(cls) -> str:
        return "sum"

    @classmethod
    def get_operator_cls(cls) -> operators.BinaryOp:
        return operators.Sum


class UnaryOpParser(OperatorParser):
    def parse(self, op_inputs: dict | list, path_op: str) -> operators.UnaryOp:
        arg = self.meta_op_parser.parse(op_inputs, path_op)
        try:
            return self.get_operator_cls()(arg)
        except TypeError as e:
            raise ParsingException(f"Error when parsing {path_op}") from e

    @classmethod
    @abc.abstractmethod
    def get_operator_cls(cls) -> operators.UnaryOp:
        pass


class NotParser(UnaryOpParser):
    @classmethod
    def get_name(cls) -> str:
        return "not"

    @classmethod
    def get_operator_cls(cls) -> operators.UnaryOp:
        return operators.Not


class ListParser(OperatorParser):
    @classmethod
    def get_name(cls) -> str:
        return "list"

    def parse(self, op_inputs: dict | list, path_op: str) -> operators.List:
        list_op = []
        for i, op in enumerate(op_inputs):
            parsed_op = self.meta_op_parser.parse(op, f"{path_op}.{i}")
            list_op.append(parsed_op)
        try:
            return operators.List(list_op)
        except TypeError as e:
            raise ParsingException(f"Error when parsing {path_op}") from e


class ForEachParser(OperatorParser):
    @classmethod
    def get_name(cls) -> str:
        return "forEach"

    def parse(self, op_inputs: dict | list, path_op: str) -> operators.ForEach:
        raw_elements = utils.must_get(op_inputs, "elements", f"In {path_op}, required 'elements'")
        elements = self.meta_op_parser.parse(raw_elements, f"{path_op}.elements")

        raw_op = utils.must_get(op_inputs, "op", f"In {path_op}, required 'op'")
        op = self.meta_op_parser.parse(raw_op, f"{path_op}.op")

        try:
            return operators.ForEach(elements, op)
        except TypeError as e:
            raise ParsingException(f"Error when parsing {path_op}") from e


class ContainParser(OperatorParser):
    @classmethod
    def get_name(cls) -> str:
        return "contain"

    def parse(self, op_inputs: dict | list, path_op: str) -> operators.Contain:
        raw_elements = utils.must_get(op_inputs, "elements", f"In {path_op}, required 'elements'")
        elements = self.meta_op_parser.parse(raw_elements, f"{path_op}.elements")

        raw_elem = utils.must_get(op_inputs, "value", f"In {path_op}, required 'value'")
        elem = self.meta_op_parser.parse(raw_elem, f"{path_op}.value")

        try:
            return operators.Contain(elements, elem)
        except TypeError as e:
            raise ParsingException(f"Error when parsing {path_op}") from e


class ConstParser(OperatorParser):
    @classmethod
    def get_name(cls) -> str:
        return "const"

    def parse(self, op_inputs: dict | list, path_op: str) -> operators.Const:
        try:
            return operators.Const(op_inputs)
        except TypeError as e:
            raise ParsingException(f"Error when parsing {path_op}") from e


class GetValueParser(OperatorParser):
    @classmethod
    def get_name(cls) -> str:
        return "getValue"

    def parse(self, op_inputs: str, path_op: str) -> operators.GetValue:
        if not isinstance(op_inputs, str):
            raise ValueError(f"Expected to find str but got {op_inputs} in {path_op}")
        try:
            return expr_parser.parse_ref(op_inputs)
        except TypeError as e:
            raise ParsingException(f"Error when parsing {path_op}") from e
