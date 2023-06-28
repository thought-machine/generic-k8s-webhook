import abc
from typing import Any

import jsonpatch

from generic_k8s_webhook.utils import to_number


class JsonPatchOperator(abc.ABC):
    def __init__(self, path: list[str]) -> None:
        self.path = path

    @abc.abstractmethod
    def generate_patch(self, json_to_patch: dict | list) -> jsonpatch.JsonPatch:
        pass


class JsonPatchAdd(JsonPatchOperator):
    def __init__(self, path: list[str], value: Any) -> None:
        super().__init__(path)
        self.value = value

    # Remember the op "add" is like an assignment
    def generate_patch(self, json_to_patch: dict | list) -> jsonpatch.JsonPatch:
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
                if key == "-":
                    new_value = [new_value]
                else:
                    new_value = {key: new_value}

        # Convert the list to a string separated by "/"
        formatted_path = "/" + "/".join(new_path)

        return jsonpatch.JsonPatch(
            [
                {
                    "op": "add",
                    "path": formatted_path,
                    "value": new_value,
                }
            ]
        )


class JsonPatchRemove(JsonPatchOperator):
    def generate_patch(self, json_to_patch: dict | list) -> jsonpatch.JsonPatch:
        # TODO If the key to remove doesn't exist, this must become a no-op
        formatted_path = "/" + "/".join(self.path)
        return jsonpatch.JsonPatch(
            [
                {
                    "op": "remove",
                    "path": formatted_path,
                }
            ]
        )


class JsonPatchReplace(JsonPatchOperator):
    def __init__(self, path: list[str], value: Any) -> None:
        super().__init__(path)
        self.value = value

    def generate_patch(self, json_to_patch: dict | list) -> jsonpatch.JsonPatch:
        formatted_path = "/" + "/".join(self.path)
        return jsonpatch.JsonPatch([{"op": "replace", "path": formatted_path, "value": self.value}])


class JsonPatchCopy(JsonPatchOperator):
    def __init__(self, path: list[str], fromm: Any) -> None:
        super().__init__(path)
        self.fromm = fromm

    def generate_patch(self, json_to_patch: dict | list) -> jsonpatch.JsonPatch:
        formatted_path = "/" + "/".join(self.path)
        formatted_from = "/" + "/".join(self.fromm)
        return jsonpatch.JsonPatch([{"op": "copy", "path": formatted_path, "from": formatted_from}])


class JsonPatchMove(JsonPatchOperator):
    def __init__(self, path: list[str], fromm: Any) -> None:
        super().__init__(path)
        self.fromm = fromm

    def generate_patch(self, json_to_patch: dict | list) -> jsonpatch.JsonPatch:
        formatted_path = "/" + "/".join(self.path)
        formatted_from = "/" + "/".join(self.fromm)
        return jsonpatch.JsonPatch([{"op": "move", "path": formatted_path, "from": formatted_from}])


class JsonPatchTest(JsonPatchOperator):
    def __init__(self, path: list[str], value: Any) -> None:
        super().__init__(path)
        self.value = value

    def generate_patch(self, json_to_patch: dict | list) -> jsonpatch.JsonPatch:
        formatted_path = "/" + "/".join(self.path)
        return jsonpatch.JsonPatch([{"op": "test", "path": formatted_path, "value": self.value}])
