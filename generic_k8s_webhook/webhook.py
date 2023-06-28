import copy

import jsonpatch

from generic_k8s_webhook.jsonpatch_helpers import JsonPatchOperator
from generic_k8s_webhook.operators import Operator
from generic_k8s_webhook.utils import convert_dot_string_path_to_list


class Action:
    def __init__(self, condition: Operator, list_jpatch_op: list[JsonPatchOperator], accept: bool) -> None:
        self.condition = condition
        self.list_jpatch_op = list_jpatch_op
        self.accept = accept

    def check_condition(self, manifest: dict) -> bool:
        return self.condition.get_value([manifest])

    def get_patches(self, manifest: dict) -> jsonpatch.JsonPatch | None:
        if not self.list_jpatch_op:
            return None

        # 1. Generate a json patch specific for the manifest
        # 2. Update the manifest based on that patch
        # 3. Extract the raw patch, so we can merge later all the patches into a single JsonPatch object
        list_raw_patches = []
        for jpatch_op in self.list_jpatch_op:
            jpatch = jpatch_op.generate_patch(manifest)
            manifest = jpatch.apply(manifest)
            list_raw_patches.extend(jpatch.patch)

        return jsonpatch.JsonPatch(list_raw_patches)


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
