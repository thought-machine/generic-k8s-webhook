import abc

from generic_k8s_webhook import jsonpatch_helpers, utils


class IJsonPatchParser(abc.ABC):
    @abc.abstractmethod
    def parse(self, raw_patch: list) -> list[jsonpatch_helpers.JsonPatchOperator]:
        pass


class JsonPatchParserV1(IJsonPatchParser):
    """Class used to parse a json patch spec V1. Example:

    ```yaml
    op: add
    path: <path>
    value: <value-to-add>
    ```
    """

    def parse(self, raw_patch: list) -> list[jsonpatch_helpers.JsonPatchOperator]:
        patch = []
        for raw_elem in raw_patch:
            op = utils.must_pop(raw_elem, "op", f"Missing key 'op' in {raw_elem}")
            if op == "add":
                path = self._parse_path(raw_elem, "path")
                value = utils.must_pop(raw_elem, "value", f"Missing key 'value' in {raw_elem}")
                parsed_elem = jsonpatch_helpers.JsonPatchAdd(path, value)
            elif op == "remove":
                path = self._parse_path(raw_elem, "path")
                parsed_elem = jsonpatch_helpers.JsonPatchRemove(path)
            elif op == "replace":
                path = self._parse_path(raw_elem, "path")
                value = utils.must_pop(raw_elem, "value", f"Missing key 'value' in {raw_elem}")
                parsed_elem = jsonpatch_helpers.JsonPatchReplace(path, value)
            elif op == "copy":
                path = self._parse_path(raw_elem, "path")
                fromm = self._parse_path(raw_elem, "from")
                parsed_elem = jsonpatch_helpers.JsonPatchCopy(path, fromm)
            elif op == "move":
                path = self._parse_path(raw_elem, "path")
                fromm = self._parse_path(raw_elem, "from")
                parsed_elem = jsonpatch_helpers.JsonPatchMove(path, fromm)
            elif op == "test":
                path = self._parse_path(raw_elem, "path")
                value = utils.must_pop(raw_elem, "value", f"Missing key 'value' in {raw_elem}")
                parsed_elem = jsonpatch_helpers.JsonPatchTest(path, value)
            else:
                raise ValueError(f"Invalid patch operation {raw_elem['op']}")

            if len(raw_elem) > 0:
                raise ValueError(f"Unexpected keys {raw_elem}")
            patch.append(parsed_elem)

        return patch

    def _parse_path(self, raw_elem: dict, key: str) -> list[str]:
        raw_path = utils.must_pop(raw_elem, key, f"Missing key {key} in {raw_elem}")
        path = utils.convert_dot_string_path_to_list(raw_path)
        if path[0] != "":
            raise ValueError(f"The first element of a path in the patch must be '.', not {path[0]}")
        return path[1:]
