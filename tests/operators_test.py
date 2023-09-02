import pytest

import generic_k8s_webhook.config_parser.expr_parser as expr_parser
import generic_k8s_webhook.config_parser.operator_parser as op_parser


def _exec_test(
    list_parsers: list[op_parser.OperatorParser],
    raw_str_parser: expr_parser.IRawStringParser,
    raw_op: dict,
    contexts: list[dict],
    expected_result,
) -> None:
    meta_op_parser = op_parser.MetaOperatorParser(list_parsers, raw_str_parser)
    op = meta_op_parser.parse(raw_op, "")
    result = op.get_value(contexts)
    assert result == expected_result


@pytest.mark.parametrize(
    ("raw_op", "expected_result"),
    [
        (
            {
                "and": [
                    {"const": True},
                    {"const": True},
                ]
            },
            True,
        ),
        (
            {
                "and": [
                    {"const": True},
                    {"const": False},
                ]
            },
            False,
        ),
        (
            {
                "and": [
                    {"const": False},
                ]
            },
            False,
        ),
        ({"and": []}, True),
    ],
)
def test_and(raw_op, expected_result):
    _exec_test([op_parser.AndParser, op_parser.ConstParser], None, raw_op, [], expected_result)


@pytest.mark.parametrize(
    ("raw_op", "expected_result"),
    [
        (
            {
                "or": [
                    {"const": False},
                    {"const": False},
                ]
            },
            False,
        ),
        (
            {
                "or": [
                    {"const": True},
                    {"const": False},
                ]
            },
            True,
        ),
        (
            {
                "or": [
                    {"const": True},
                ]
            },
            True,
        ),
        ({"or": []}, True),
    ],
)
def test_or(raw_op, expected_result):
    _exec_test([op_parser.OrParser, op_parser.ConstParser], None, raw_op, [], expected_result)


@pytest.mark.parametrize(
    ("raw_op", "expected_result"),
    [
        ({"not": {"const": True}}, False),
    ],
)
def test_not(raw_op, expected_result):
    _exec_test([op_parser.NotParser, op_parser.ConstParser], None, raw_op, [], expected_result)


@pytest.mark.parametrize(
    ("raw_op", "expected_result"),
    [
        (
            {
                "equal": [
                    {"const": 1},
                ]
            },
            True,
        ),
        (
            {
                "equal": [
                    {"const": 2},
                    {"const": 3},
                ]
            },
            False,
        ),
        (
            {
                "equal": [
                    {"const": 4},
                    {"const": 4},
                ]
            },
            True,
        ),
        ({"equal": []}, True),
    ],
)
def test_equal(raw_op, expected_result):
    _exec_test([op_parser.EqualParser, op_parser.ConstParser], None, raw_op, [], expected_result)


@pytest.mark.parametrize(
    ("raw_op", "expected_result"),
    [
        (
            {
                "sum": [
                    {"const": 2},
                    {"const": 3},
                    {"const": 4},
                ]
            },
            9,
        ),
        (
            {
                "sum": [
                    {"const": 2},
                ]
            },
            2,
        ),
        ({"sum": []}, 0),
    ],
)
def test_sum(raw_op, expected_result):
    _exec_test([op_parser.SumParser, op_parser.ConstParser], None, raw_op, [], expected_result)


@pytest.mark.parametrize(
    ("name", "raw_op", "contexts", "expected_result"),
    [
        (
            "Retrieve value from last context",
            {"getValue": ".name"},
            [
                {"metadata": {"name": "foo"}, "spec": {}},
                {"name": "bar"},
            ],
            "bar",
        ),
        (
            "Retrieve value from first context",
            {"getValue": "$.metadata.name"},
            [
                {"metadata": {"name": "foo"}, "spec": {}},
                {"name": "bar"},
            ],
            "foo",
        ),
    ],
)
def test_getvalue(name, raw_op, contexts, expected_result):
    _exec_test([op_parser.GetValueParser], None, raw_op, contexts, expected_result)


@pytest.mark.parametrize(
    ("name", "raw_op", "contexts", "expected_result"),
    [
        (
            "Iterate over a constant list of elements and sum 10 to each",
            {
                "forEach": {
                    "elements": {
                        "const": [
                            1,
                            2,
                        ]
                    },
                    "op": {
                        "sum": [
                            {"const": 10},
                            {"getValue": "."},
                        ]
                    },
                }
            },
            [],
            [11, 12],
        ),
        (
            "Iterate over a list defined in the yaml file and sum 1 to each",
            {
                "forEach": {
                    "elements": {"getValue": ".containers"},
                    "op": {
                        "sum": [
                            {"const": 1},
                            {"getValue": ".maxCPU"},
                        ]
                    },
                }
            },
            [{"containers": [{"maxCPU": 1}, {"maxCPU": 2}]}],
            [2, 3],
        ),
    ],
)
def test_foreach(name, raw_op, contexts, expected_result):
    parsers = [op_parser.ForEachParser, op_parser.GetValueParser, op_parser.SumParser, op_parser.ConstParser]
    _exec_test(parsers, None, raw_op, contexts, expected_result)


@pytest.mark.parametrize(
    ("name", "raw_op", "contexts", "expected_result"),
    [
        (
            "The list contains the element",
            {"contain": {"elements": {"getValue": ".containers"}, "value": {"const": {"maxCPU": 2}}}},
            [{"containers": [{"maxCPU": 1}, {"maxCPU": 2}]}],
            True,
        ),
        (
            "The list doesn't contain the element",
            {"contain": {"elements": {"getValue": ".containers"}, "value": {"const": {"maxCPU": 4}}}},
            [{"containers": [{"maxCPU": 1}, {"maxCPU": 2}]}],
            False,
        ),
    ],
)
def test_contain(name, raw_op, contexts, expected_result):
    parsers = [op_parser.ContainParser, op_parser.GetValueParser, op_parser.ConstParser]
    _exec_test(parsers, None, raw_op, contexts, expected_result)


@pytest.mark.parametrize(
    ("name", "raw_op", "contexts", "expected_result"),
    [
        (
            "Arithmetic operations",
            "2 * (3 + 4 / 2) - 1",
            [],
            9,
        ),
        (
            "Arithmetic operations",
            "2*(3+4/2)-1",
            [],
            9,
        ),
        (
            "Arithmetic operations",
            "8/4/2",
            [],
            1,
        ),
        (
            "Boolean operations and comp",
            "1 == 1 && 1 != 0 && 0 <= 0 && 0 < 1 && 1 > 0 && 1 >= 1 && true",
            [],
            True,
        ),
        (
            "Boolean operations and comp",
            "1 != 1 || 1 == 0 || 0 < 0 || 0 >= 1 || 1 <= 0 || 1 < 1 || false",
            [],
            False,
        ),
        (
            "String comp",
            '"foo" == "foo" && "foo" != "bar"',
            [],
            True,
        ),
        (
            "Reference",
            ".containers.0.maxCPU + 1  == .containers.1.maxCPU",
            [{"containers": [{"maxCPU": 1}, {"maxCPU": 2}]}],
            True,
        ),
    ],
)
def test_raw_str_expr(name, raw_op, contexts, expected_result):
    _exec_test([], expr_parser.RawStringParserV1(), raw_op, contexts, expected_result)
