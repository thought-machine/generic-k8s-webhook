import pytest

from generic_k8s_webhook.config_parser import JsonPatchParser


@pytest.mark.parametrize(
    ("name", "json_to_patch", "patch", "expected_result"),
    [
        (
            "Change the value of a simple key",
            {"spec": {}, "metadata": {}},
            [{"op": "add", "path": ".spec", "value": "foo"}],
            {"spec": "foo", "metadata": {}},
        ),
        (
            "Add a subkey that doesn't exist",
            {"spec": {}, "metadata": {}},
            [{"op": "add", "path": ".spec.subkey", "value": "foo"}],
            {"spec": {"subkey": "foo"}, "metadata": {}},
        ),
        (
            "Add a 2 subkeys that don't exist",
            {"spec": {}, "metadata": {}},
            [{"op": "add", "path": ".spec.subkey1.subkey2", "value": "foo"}],
            {"spec": {"subkey1": {"subkey2": "foo"}}, "metadata": {}},
        ),
        (
            "Add an element to an existing empty list",
            {"spec": {"containers": []}, "metadata": {}},
            [{"op": "add", "path": ".spec.containers.-", "value": {"name": "main"}}],
            {"spec": {"containers": [{"name": "main"}]}, "metadata": {}},
        ),
        (
            "Add an element to an existing non-empty list",
            {"spec": {"containers": [{"name": "sidecar"}]}, "metadata": {}},
            [{"op": "add", "path": ".spec.containers.-", "value": {"name": "main"}}],
            {"spec": {"containers": [{"name": "sidecar"}, {"name": "main"}]}, "metadata": {}},
        ),
        (
            "Add an element to a non-existing list",
            {"spec": {}, "metadata": {}},
            [{"op": "add", "path": ".spec.containers.-", "value": {"name": "main"}}],
            {"spec": {"containers": [{"name": "main"}]}, "metadata": {}},
        ),
        (
            "Add a new entry on the second element of the list",
            {"spec": {"containers": [{"name": "main"}]}, "metadata": {}},
            [{"op": "add", "path": ".spec.containers.0.metadata", "value": {}}],
            {"spec": {"containers": [{"name": "main", "metadata": {}}]}, "metadata": {}},
        ),
    ],
)
def test_add(name, json_to_patch, patch, expected_result):
    assert all(elem["op"] == "add" for elem in patch)
    patcher = JsonPatchParser.parse(patch)[0]
    processed_patch = patcher.generate_patch(json_to_patch)
    patched_json = processed_patch.apply(json_to_patch)
    assert patched_json == expected_result


@pytest.mark.parametrize(
    ("name", "json_to_patch", "patch", "expected_result"),
    [
        (
            "Remove the value of a simple key",
            {"spec": {}, "metadata": {}},
            [
                {
                    "op": "remove",
                    "path": ".spec",
                }
            ],
            {"metadata": {}},
        ),
        # (
        #     "Remove a key that doesn't exist",
        #     {"spec": {}, "metadata": {}},
        #     [{
        #         "op": "remove",
        #         "path": ".status",
        #     }],
        #     {"spec": {}, "metadata": {}}
        # ),
    ],
)
def test_remove(name, json_to_patch, patch, expected_result):
    assert all(elem["op"] == "remove" for elem in patch)
    patcher = JsonPatchParser.parse(patch)[0]
    processed_patch = patcher.generate_patch(json_to_patch)
    patched_json = processed_patch.apply(json_to_patch)
    assert patched_json == expected_result


@pytest.mark.parametrize(
    ("name", "json_to_patch", "patch", "expected_result"),
    [
        (
            "Replace the value of a simple key",
            {"spec": {}, "metadata": {"name": "foo"}},
            [{"op": "replace", "path": ".metadata.name", "value": "bar"}],
            {"spec": {}, "metadata": {"name": "bar"}},
        ),
    ],
)
def test_replace(name, json_to_patch, patch, expected_result):
    assert all(elem["op"] == "replace" for elem in patch)
    patcher = JsonPatchParser.parse(patch)[0]
    processed_patch = patcher.generate_patch(json_to_patch)
    patched_json = processed_patch.apply(json_to_patch)
    assert patched_json == expected_result


@pytest.mark.parametrize(
    ("name", "json_to_patch", "patch", "expected_result"),
    [
        (
            "Copy the value from a simple key to another",
            {"spec": {"containers": [{"name": "bar"}]}, "metadata": {"name": "foo"}},
            [{"op": "copy", "path": ".metadata.name", "from": ".spec.containers.0.name"}],
            {"spec": {"containers": [{"name": "bar"}]}, "metadata": {"name": "bar"}},
        ),
    ],
)
def test_copy(name, json_to_patch, patch, expected_result):
    assert all(elem["op"] == "copy" for elem in patch)
    patcher = JsonPatchParser.parse(patch)[0]
    processed_patch = patcher.generate_patch(json_to_patch)
    patched_json = processed_patch.apply(json_to_patch)
    assert patched_json == expected_result


@pytest.mark.parametrize(
    ("name", "json_to_patch", "patch", "expected_result"),
    [
        (
            "Move the value from a simple key to another",
            {"spec": {"containers": [{"name": "bar"}]}, "metadata": {"name": "foo"}},
            [{"op": "move", "path": ".metadata.name", "from": ".spec.containers.0.name"}],
            {"spec": {"containers": [{}]}, "metadata": {"name": "bar"}},
        ),
    ],
)
def test_move(name, json_to_patch, patch, expected_result):
    assert all(elem["op"] == "move" for elem in patch)
    patcher = JsonPatchParser.parse(patch)[0]
    processed_patch = patcher.generate_patch(json_to_patch)
    patched_json = processed_patch.apply(json_to_patch)
    assert patched_json == expected_result


@pytest.mark.parametrize(
    ("name", "json_to_patch", "patch", "expected_result"),
    [
        (
            "Test the value of a simple key",
            {"spec": {}, "metadata": {"name": "foo"}},
            [{"op": "test", "path": ".metadata.name", "value": "foo"}],
            {"spec": {}, "metadata": {"name": "foo"}},
        ),
    ],
)
def test_test(name, json_to_patch, patch, expected_result):
    assert all(elem["op"] == "test" for elem in patch)
    patcher = JsonPatchParser.parse(patch)[0]
    processed_patch = patcher.generate_patch(json_to_patch)
    patched_json = processed_patch.apply(json_to_patch)
    assert patched_json == expected_result
