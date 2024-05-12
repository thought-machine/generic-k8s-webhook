import abc

import generic_k8s_webhook.config_parser.operator_parser as op_parser
from generic_k8s_webhook import jsonpatch_helpers, operators, utils
from generic_k8s_webhook.config_parser.common import ParsingException


class ParserOp(abc.ABC):
    @abc.abstractmethod
    def parse(self, raw_elem: dict, path_op: str) -> jsonpatch_helpers.JsonPatchOperator:
        pass

    def _parse_path(self, raw_elem: dict, key: str) -> list[str]:
        raw_path = utils.must_pop(raw_elem, key, f"Missing key {key} in {raw_elem}")
        path = utils.convert_dot_string_path_to_list(raw_path)
        if path[0] != "":
            raise ValueError(f"The first element of a path in the patch must be '.', not {path[0]}")
        return path[1:]


class IJsonPatchParser(abc.ABC):
    def parse(self, raw_patch: list, path_op: str) -> list[jsonpatch_helpers.JsonPatchOperator]:
        patch = []
        dict_parse_op = self._get_dict_parse_op()
        for i, raw_elem in enumerate(raw_patch):
            op = utils.must_pop(raw_elem, "op", f"Missing key 'op' in {raw_elem}")

            # Select the appropiate class needed to parse the operation "op"
            if op not in dict_parse_op:
                raise ParsingException(f"Unsupported patch operation {op} on {path_op}")
            parse_op = dict_parse_op[op]
            try:
                parsed_elem = parse_op.parse(raw_elem, f"{path_op}.{i}")
            except Exception as e:
                raise ParsingException(f"Error when parsing {path_op}") from e

            # Make sure we have extracted all the keys from "raw_elem"
            if len(raw_elem) > 0:
                raise ValueError(f"Unexpected keys {raw_elem}")
            patch.append(parsed_elem)

        return patch

    @abc.abstractmethod
    def _get_dict_parse_op(self) -> dict[str, ParserOp]:
        """A dictionary with the classes that can parse the json patch operations
        supported by this JsonPatchParser
        """


class ParseAdd(ParserOp):
    def parse(self, raw_elem: dict, path_op: str) -> jsonpatch_helpers.JsonPatchOperator:
        path = self._parse_path(raw_elem, "path")
        value = utils.must_pop(raw_elem, "value", f"Missing key 'value' in {raw_elem}")
        return jsonpatch_helpers.JsonPatchAdd(path, value)


class ParseRemove(ParserOp):
    def parse(self, raw_elem: dict, path_op: str) -> jsonpatch_helpers.JsonPatchOperator:
        path = self._parse_path(raw_elem, "path")
        return jsonpatch_helpers.JsonPatchRemove(path)


class ParseReplace(ParserOp):
    def parse(self, raw_elem: dict, path_op: str) -> jsonpatch_helpers.JsonPatchOperator:
        path = self._parse_path(raw_elem, "path")
        value = utils.must_pop(raw_elem, "value", f"Missing key 'value' in {raw_elem}")
        return jsonpatch_helpers.JsonPatchReplace(path, value)


class ParseCopy(ParserOp):
    def parse(self, raw_elem: dict, path_op: str) -> jsonpatch_helpers.JsonPatchOperator:
        path = self._parse_path(raw_elem, "path")
        fromm = self._parse_path(raw_elem, "from")
        return jsonpatch_helpers.JsonPatchCopy(path, fromm)


class ParseMove(ParserOp):
    def parse(self, raw_elem: dict, path_op: str) -> jsonpatch_helpers.JsonPatchOperator:
        path = self._parse_path(raw_elem, "path")
        fromm = self._parse_path(raw_elem, "from")
        return jsonpatch_helpers.JsonPatchMove(path, fromm)


class ParseTest(ParserOp):
    def parse(self, raw_elem: dict, path_op: str) -> jsonpatch_helpers.JsonPatchOperator:
        path = self._parse_path(raw_elem, "path")
        value = utils.must_pop(raw_elem, "value", f"Missing key 'value' in {raw_elem}")
        return jsonpatch_helpers.JsonPatchTest(path, value)


class ParseExpr(ParserOp):
    def __init__(self, meta_op_parser: op_parser.MetaOperatorParser) -> None:
        self.meta_op_parser = meta_op_parser

    def parse(self, raw_elem: dict, path_op: str) -> jsonpatch_helpers.JsonPatchOperator:
        path = self._parse_path(raw_elem, "path")
        value = utils.must_pop(raw_elem, "value", f"Missing key 'value' in {raw_elem}")
        operator = self.meta_op_parser.parse(value, f"{path_op}.value")
        return jsonpatch_helpers.JsonPatchExpr(path, operator)


class ParseForEach(ParserOp):
    def __init__(self, meta_op_parser: op_parser.MetaOperatorParser, jsonpatch_parser: IJsonPatchParser) -> None:
        self.meta_op_parser = meta_op_parser
        self.jsonpatch_parser = jsonpatch_parser

    def parse(self, raw_elem: dict, path_op: str) -> jsonpatch_helpers.JsonPatchOperator:
        elems = utils.must_pop(raw_elem, "elements", f"Missing key 'elements' in {raw_elem}")
        op = self.meta_op_parser.parse(elems, f"{path_op}.elements")
        if not isinstance(op, operators.OperatorWithRef):
            raise ParsingException(
                f"The expression in {path_op}.elements must reference elements in the json that we want to patch"
            )
        list_raw_patch = utils.must_pop(raw_elem, "patch", f"Missing key 'patch' in {raw_elem}")
        if not isinstance(list_raw_patch, list):
            raise ParsingException(f"In {path_op}.patch we expect a list of patch, but got {list_raw_patch}")
        jsonpatch_op = self.jsonpatch_parser.parse(list_raw_patch, f"{path_op}.patch")
        return jsonpatch_helpers.JsonPatchForEach(op, jsonpatch_op)


class JsonPatchParserV1(IJsonPatchParser):
    """Class used to parse a json patch spec V1. Example:

    ```yaml
    op: add
    path: <path>
    value: <value-to-add>
    ```
    """

    def _get_dict_parse_op(self) -> dict[str, ParserOp]:
        return {
            "add": ParseAdd(),
            "remove": ParseRemove(),
            "replace": ParseReplace(),
            "copy": ParseCopy(),
            "move": ParseMove(),
            "test": ParseTest(),
        }


class JsonPatchParserV2(JsonPatchParserV1):
    """Class used to parse a json patch spec V2. It supports the same actions as the
    json patch patch spec V1 plus the ability use expressions to create new values
    """

    def __init__(self, meta_op_parser: op_parser.MetaOperatorParser) -> None:
        self.meta_op_parser = meta_op_parser

    def _get_dict_parse_op(self) -> dict[str, ParserOp]:
        dict_parse_op_v1 = super()._get_dict_parse_op()
        dict_parse_op_v2 = {"expr": ParseExpr(self.meta_op_parser), "forEach": ParseForEach(self.meta_op_parser, self)}
        return {**dict_parse_op_v1, **dict_parse_op_v2}
