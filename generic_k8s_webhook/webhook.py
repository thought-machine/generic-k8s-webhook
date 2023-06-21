import copy
import jsonpatch
from generic_k8s_webhook.operators import Operator


class Action:
    def __init__(self, condition: Operator, patch: dict, accept: bool) -> None:
        self.condition = condition
        self.patch = patch
        self.accept = accept

    def check_condition(self, manifest: dict) -> bool:
        return self.condition.get_value([manifest])

    def get_patches(self, manifest: dict) -> jsonpatch.JsonPatch:
        if not self.patch:
            return None

        # TODO This needs much better robustness and error handling
        formatted_patch = copy.deepcopy(self.patch)
        for key in ["path", "from"]:
            if key in formatted_patch:
                formatted_patch[key] = "/" + formatted_patch[key][1:]
        return jsonpatch.JsonPatch([formatted_patch])


class Webhook:
    def __init__(self, name: str, path: str, list_actions: list[Action]) -> None:
        self.name = name
        self.path = path
        self.list_actions = list_actions

    def process_manifest(self, manifest: dict) -> tuple[bool, jsonpatch.JsonPatch]:
        for action in self.list_actions:
            if action.check_condition(manifest):
                patches = action.get_patches(manifest)
                return action.accept, patches

        # If no condition is met, we'll accept the manifest without any patch
        return True, None
