import pytest
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")

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
    ),
    (
        "not",
        {"const": True},
        False
    ),
    (
        "sum",
        [
            {"const": 2},
            {"const": 3},
            {"const": 4},
        ],
        9
    )
])
def test_basic_operators(op, inputs, expected_result):
    op = ops.parse_operator({op: inputs})
    result = op.get_value([])
    assert result == expected_result


@pytest.mark.parametrize(("name", "contexts", "path", "expected_result"), [
    (
        "Retrieve value from last context",
        [
            {
                "metadata": {"name": "foo"},
                "spec": {}
            },
            {
                "name": "bar"
            },
        ],
        ".name",
        "bar",
    ),
    (
        "Retrieve value from first context",
        [
            {
                "metadata": {"name": "foo"},
                "spec": {}
            },
            {
                "name": "bar"
            },
        ],
        "$.metadata.name",
        "foo",
    ),
])
def test_path(name, contexts, path, expected_result):
    op = ops.parse_operator({"getValue": path})
    result = op.get_value(contexts)
    assert result == expected_result


@pytest.mark.parametrize(("name", "contexts", "inputs", "expected_result"), [
    (
        "Iterate over a constant list of elements and sum 10 to each",
        [],
        {
            "elements": {"const": [
                1,
                2,
            ]},
            "op": {
                "sum": [
                    {"const": 10},
                    {"getValue": "."},
                ]
            }
        },
        [11, 12],
    ),
    (
        "Iterate over a list defined in the yaml file and sum 1 to each",
        [{
            "containers": [
                {"maxCPU": 1},
                {"maxCPU": 2}
            ]
        }],
        {
            "elements": {"getValue": ".containers"},
            "op": {
                "sum": [
                    {"const": 1},
                    {"getValue": ".maxCPU"},
                ]
            }
        },
        [2, 3],
    ),
])
def test_foreach(name, contexts, inputs, expected_result):
    op = ops.parse_operator({"forEach": inputs})
    result = op.get_value(contexts)
    assert result == expected_result


@pytest.mark.parametrize(("name", "contexts", "inputs", "expected_result"), [
    (
        "The list contains the element",
        [{
            "containers": [
                {"maxCPU": 1},
                {"maxCPU": 2}
            ]
        }],
        {
            "elements": {"getValue": ".containers"},
            "value": {
                "const": {"maxCPU": 2}
            }
        },
        True,
    ),
    (
        "The list doesn't contain the element",
        [{
            "containers": [
                {"maxCPU": 1},
                {"maxCPU": 2}
            ]
        }],
        {
            "elements": {"getValue": ".containers"},
            "value": {
                "const": {"maxCPU": 4}
            }
        },
        False,
    ),
])
def test_contain(name, contexts, inputs, expected_result):
    op = ops.parse_operator({"contain": inputs})
    result = op.get_value(contexts)
    assert result == expected_result
