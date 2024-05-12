import abc
import ast

from lark import Lark, Transformer

import generic_k8s_webhook.operators as op
from generic_k8s_webhook import utils

GRAMMAR_V1 = r"""
    ?start: expr | list_filter_map

    ?list_filter_map: reference filter_expr -> filterr
        | reference map_expr -> mapp
        | list_filter_map filter_expr -> filterr
        | list_filter_map map_expr -> mapp

    ?filter_expr: "|" expr

    ?map_expr: "->" expr

    ?expr: or

    ?or: and
        | or "||" and       -> orr

    ?and: comp
        | and "&&" comp     -> andd

    ?comp: sum
        | sum "==" sum      -> eq
        | sum "!=" sum      -> ne
        | sum "<=" sum      -> le
        | sum ">=" sum      -> ge
        | sum "<" sum       -> lt
        | sum ">" sum       -> gt

    ?sum: product
        | sum "+" product   -> add
        | sum "-" product   -> sub
        | sum "++" product  -> strconcat

    ?product: atom
        | product "*" atom  -> mul
        | product "/" atom  -> div

    ?atom: signed_number
        | escaped_string
        | reference
        | bool
        | "(" expr ")"

    signed_number: SIGNED_NUMBER    -> number
    escaped_string: ESCAPED_STRING  -> const_string
    reference: REF                  -> ref
    bool: BOOL                      -> boolean

    BOOL: "true" | "false"
    REF: "$"? ("."(CNAME|"*"|INT))+

    %import common.CNAME
    %import common.SIGNED_NUMBER
    %import common.ESCAPED_STRING
    %import common.WS_INLINE
    %import common.INT

    %ignore WS_INLINE
"""


class MyTransformerV1(Transformer):
    def orr(self, items):
        return op.Or(op.List(items))

    def andd(self, items):
        return op.And(op.List(items))

    def eq(self, items):
        return op.Equal(op.List(items))

    def ne(self, items):
        return op.NotEqual(op.List(items))

    def le(self, items):
        return op.LessOrEqual(op.List(items))

    def ge(self, items):
        return op.GreaterOrEqual(op.List(items))

    def lt(self, items):
        return op.LessThan(op.List(items))

    def gt(self, items):
        return op.GreaterThan(op.List(items))

    def add(self, items):
        return op.Sum(op.List(items))

    def sub(self, items):
        return op.Sub(op.List(items))

    def strconcat(self, items):
        return op.StrConcat(op.List(items))

    def mul(self, items):
        return op.Mul(op.List(items))

    def div(self, items):
        return op.Div(op.List(items))

    def number(self, items):
        (elem,) = items
        try:
            elem_number = int(elem)
        except ValueError:
            elem_number = float(elem)
        return op.Const(elem_number)

    def const_string(self, items):
        (elem,) = items
        # This evaluates the double-quoted string, so the initial and ending double quotes disappear
        # and any escaped char is also converted. For example, \" -> "
        elem_str = ast.literal_eval(elem)
        return op.Const(elem_str)

    def ref(self, items):
        (elem,) = items
        return parse_ref(elem)

    def boolean(self, items):
        (elem,) = items
        elem_bool = elem == "true"
        return op.Const(elem_bool)

    def filterr(self, items):
        elems, operator = items
        return op.Filter(elems, operator)

    def mapp(self, items):
        elems, operator = items
        return op.ForEach(elems, operator)


def parse_ref(ref: str) -> op.GetValue:
    """Parses a string that is a reference to some element within a json payload
    and returns a GetValue object.

    Args:
        ref (str): The reference to a field in a json payload
    """
    # Convert, for example, `.foo.bar` into ["foo", "bar"]
    path = utils.convert_dot_string_path_to_list(ref)

    # Get the id of the context that it will use
    if path[0] == "":
        context_id = -1
    elif path[0] == "$":
        context_id = 0
    else:
        raise ValueError(f"Invalid {path[0]} in {ref}")
    return op.GetValue(path[1:], context_id)


class IRawStringParser(abc.ABC):
    def __init__(self) -> None:
        self.parser = Lark(self.get_grammar())
        self.transformer = self.get_transformer()

    def parse(self, raw_string: str) -> op.Operator:
        tree = self.parser.parse(raw_string)
        operator = self.transformer.transform(tree)
        return operator

    @classmethod
    @abc.abstractmethod
    def get_grammar(cls) -> str:
        pass

    @classmethod
    @abc.abstractmethod
    def get_transformer(cls) -> Transformer:
        pass


class RawStringParserNotImplemented(IRawStringParser):
    def __init__(self) -> None:  # pylint: disable=super-init-not-called
        # Empty method
        pass

    def parse(self, raw_string: str) -> op.Operator:
        return NotImplementedError("Parsing string expressions is not supported")

    @classmethod
    def get_grammar(cls) -> str:
        return ""

    @classmethod
    def get_transformer(cls) -> Transformer:
        return Transformer()


class RawStringParserV1(IRawStringParser):
    @classmethod
    def get_grammar(cls) -> str:
        return GRAMMAR_V1

    @classmethod
    def get_transformer(cls) -> Transformer:
        return MyTransformerV1()


def main():
    parser = Lark(GRAMMAR_V1)
    # print(parser.parse('.key != "some string"').pretty())
    tree = parser.parse('.spec.containers | .name != "main" -> .requests.cpu * 0.75')
    print(tree.pretty())
    trans = MyTransformerV1()
    new_op = trans.transform(tree)
    print(new_op)
    context = {"spec": {"containers": [{"name": "main"}, {"name": "side", "requests": {"cpu": 2}}]}}
    print(new_op.get_value([context]))


if __name__ == "__main__":
    main()
