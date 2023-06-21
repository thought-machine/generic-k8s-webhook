import copy
import jsonpatch
from generic_k8s_webhook.operators import Operator
from generic_k8s_webhook.utils import convert_dot_string_path_to_list


class Action:
    def __init__(self, condition: Operator, patch: list[dict], accept: bool) -> None:
        self.condition = condition
        self.patch = patch
        self.accept = accept

    def check_condition(self, manifest: dict) -> bool:
        return self.condition.get_value([manifest])

    def get_patches(self, manifest: dict) -> jsonpatch.JsonPatch | None:
        if not self.patch:
            return None

        # TODO This needs much better robustness and error handling
        formatted_patch = copy.deepcopy(self.patch)
        for operation in formatted_patch:
            for key in ["path", "from"]:
                if key in operation:
                    path_list = convert_dot_string_path_to_list(operation[key])
                    operation[key] = "/" + "/".join(path_list[1:])
        return jsonpatch.JsonPatch(formatted_patch)


class Webhook:
    def __init__(self, name: str, path: str, list_actions: list[Action]) -> None:
        self.name = name
        self.path = path
        self.list_actions = list_actions

    def process_manifest(self, manifest: dict) -> tuple[bool, jsonpatch.JsonPatch | None]:
        for action in self.list_actions:
            if action.check_condition(manifest):
                patches = action.get_patches(manifest)
                return action.accept, patches

        # If no condition is met, we'll accept the manifest without any patch
        return True, None
