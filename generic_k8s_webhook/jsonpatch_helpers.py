import abc
from typing import Any, Union

import jsonpatch

from generic_k8s_webhook import operators
from generic_k8s_webhook.utils import to_number


class JsonPatchOperator(abc.ABC):
    def __init__(self, path: list[str]) -> None:
        self.path = path

    @abc.abstractmethod
    def generate_patch(self, contexts: list[Union[list, dict]], prefix: list[str] = None) -> jsonpatch.JsonPatch:
        pass

    def _format_path(self, path: list[str], prefix: list[str]) -> str:
        """Converts the `path` to a string separated by "/" and starts also by "/"
        If a prefix is defined and the path is not absolute, then the prefix is preprended.
        An absolute path is one whose first element is "$"
        """
        if path[0] == "$":
            final_path = path[1:]
        elif prefix:
            final_path = prefix + path
        else:
            final_path = path
        final_path = [str(elem) for elem in final_path]
        return "/" + "/".join(final_path)


class JsonPatchAdd(JsonPatchOperator):
    def __init__(self, path: list[str], value: Any) -> None:
        super().__init__(path)
        self.value = value

    # Remember the op "add" is like an assignment
    def generate_patch(self, contexts: list[Union[list, dict]], prefix: list[str] = None) -> jsonpatch.JsonPatch:
        json_to_patch = contexts[-1]
        # Check how many (nested) keys already exist
        existing_path = []
        first_non_existing_key = None
        for key in self.path:
            if isinstance(json_to_patch, dict):
                if key not in json_to_patch:
                    first_non_existing_key = key
                    break
                json_to_patch = json_to_patch[key]

            elif isinstance(json_to_patch, list):
                # This special case happens when we want to add an element to an existing list
                # path: /key1/key2/-
                if key == "-":
                    existing_path.append(key)
                    break

                idx = to_number(key)
                if idx > len(json_to_patch):
                    first_non_existing_key = idx
                    break
                json_to_patch = json_to_patch[idx]

            else:
                raise RuntimeError(f"Expecting dict or list, but got {json_to_patch}")

            existing_path.append(key)

        # We can only have one non-existing key in the "path"
        # The other ones must wrap the "value"
        new_path = existing_path
        new_value = self.value

        if first_non_existing_key is not None:
            # The first non-existing key must go to the "path"
            new_path += [first_non_existing_key]
            # The rest of non-existing keys must be part of the "values"
            items_to_create = self.path[len(new_path) :]
            for key in reversed(items_to_create):
                if key in ["-", "0"]:
                    new_value = [new_value]
                else:
                    new_value = {key: new_value}

        return jsonpatch.JsonPatch(
            [
                {
                    "op": "add",
                    "path": self._format_path(new_path, prefix),
                    "value": new_value,
                }
            ]
        )


class JsonPatchRemove(JsonPatchOperator):
    def generate_patch(self, contexts: list[Union[list, dict]], prefix: list[str] = None) -> jsonpatch.JsonPatch:
        # TODO If the key to remove doesn't exist, this must become a no-op
        return jsonpatch.JsonPatch(
            [
                {
                    "op": "remove",
                    "path": self._format_path(self.path, prefix),
                }
            ]
        )


class JsonPatchReplace(JsonPatchOperator):
    def __init__(self, path: list[str], value: Any) -> None:
        super().__init__(path)
        self.value = value

    def generate_patch(self, contexts: list[Union[list, dict]], prefix: list[str] = None) -> jsonpatch.JsonPatch:
        return jsonpatch.JsonPatch(
            [{"op": "replace", "path": self._format_path(self.path, prefix), "value": self.value}]
        )


class JsonPatchCopy(JsonPatchOperator):
    def __init__(self, path: list[str], fromm: Any) -> None:
        super().__init__(path)
        self.fromm = fromm

    def generate_patch(self, contexts: list[Union[list, dict]], prefix: list[str] = None) -> jsonpatch.JsonPatch:
        return jsonpatch.JsonPatch(
            [
                {
                    "op": "copy",
                    "path": self._format_path(self.path, prefix),
                    "from": self._format_path(self.fromm, prefix),
                }
            ]
        )


class JsonPatchMove(JsonPatchOperator):
    def __init__(self, path: list[str], fromm: Any) -> None:
        super().__init__(path)
        self.fromm = fromm

    def generate_patch(self, contexts: list[Union[list, dict]], prefix: list[str] = None) -> jsonpatch.JsonPatch:
        return jsonpatch.JsonPatch(
            [
                {
                    "op": "move",
                    "path": self._format_path(self.path, prefix),
                    "from": self._format_path(self.fromm, prefix),
                }
            ]
        )


class JsonPatchTest(JsonPatchOperator):
    def __init__(self, path: list[str], value: Any) -> None:
        super().__init__(path)
        self.value = value

    def generate_patch(self, contexts: list[Union[list, dict]], prefix: list[str] = None) -> jsonpatch.JsonPatch:
        return jsonpatch.JsonPatch([{"op": "test", "path": self._format_path(self.path, prefix), "value": self.value}])


class JsonPatchExpr(JsonPatchOperator):
    """It's similar to the JsonPatchAdd, but it first dynamically evaluates the actual value
    expressed under the "value" keyword and then performs a normal "add" operation using
    this new value
    """

    def __init__(self, path: list[str], value: operators.Operator) -> None:
        super().__init__(path)
        self.value = value

    def generate_patch(self, contexts: list[Union[list, dict]], prefix: list[str] = None) -> jsonpatch.JsonPatch:
        actual_value = self.value.get_value(contexts)
        json_patch_add = JsonPatchAdd(self.path, actual_value)
        return json_patch_add.generate_patch(contexts, prefix)


class JsonPatchForEach(JsonPatchOperator):
    """Generates a jsonpatch for each element from a list"""

    def __init__(self, op_with_ref: operators.OperatorWithRef, list_jsonpatch_op: list[JsonPatchOperator]) -> None:
        super().__init__([])
        self.op_with_ref = op_with_ref
        self.list_jsonpatch_op = list_jsonpatch_op

    def generate_patch(self, contexts: list[Union[list, dict]], prefix: list[str] = None) -> jsonpatch.JsonPatch:
        list_raw_patch = []
        for payload, path in self.op_with_ref.get_value_with_ref(contexts):
            for jsonpatch_op in self.list_jsonpatch_op:
                patch_obj = jsonpatch_op.generate_patch(contexts + [payload], path)
                list_raw_patch.extend(patch_obj.patch)
        return jsonpatch.JsonPatch(list_raw_patch)
