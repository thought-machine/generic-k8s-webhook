import pytest
import generic_k8s_webhook.operators as ops


@pytest.mark.parametrize(("op", "inputs", "expected_result"), [
    (
        "and",
        [
            {"const": True},
            {"const": True},
        ],
        True
    ),
    (
        "and",
        [
            {"const": True},
            {"const": False},
        ],
        False
    ),
    (
        "or",
        [
            {"const": False},
            {"const": False},
        ],
        False
    ),
    (
        "or",
        [
            {"const": True},
            {"const": False},
        ],
        True
    )
])
def test_basic_operators(op, inputs, expected_result):
    op = ops.parse_operator({op: inputs})
    result = op.get_value([])
    assert result == expected_result


@pytest.mark.parametrize(("context", "path", "expected_result"), [
    (
        {
            "metadata": {"name": "foo"},
            "spec": {}
        },
        ".metadata.name",
        "foo",
    ),
])
def test_path(context, path, expected_result):
    op = ops.parse_operator({"path": path})
    if isinstance(context, list):
        result = op.get_value(context)
    else:
        result = op.get_value([context])
    assert result == expected_result
