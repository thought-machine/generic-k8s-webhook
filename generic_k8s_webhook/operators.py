import abc
from numbers import Number
from typing import Any, Union, get_args, get_origin

from generic_k8s_webhook.utils import to_number

# Make Number callable, so it can convert, for example, a string into an int or float
Number.__call__ = to_number


class Operator(abc.ABC):
    @abc.abstractmethod
    def __init__(self, op_inputs: Any, path_op: str) -> None:
        pass

    @abc.abstractmethod
    def input_type(self) -> type | None:
        pass

    @abc.abstractmethod
    def return_type(self) -> type | None:
        pass

    @abc.abstractmethod
    def get_value(self, contexts: list):
        pass


# It's the base class for operators like and, or, sum, etc.
# Even if it's called BinaryOp, it supports a list of arguments of any size
# For example: and(true, false, true, true) -> false
class BinaryOp(Operator):
    def __init__(self, args: Operator) -> None:
        self.args = args
        # A None return type of the arguments means that this type is not defined at "compile" time
        # A list[None] for the input_type means that this operation can potentially consume any type
        # A list[None] for the args.return_type means that we can get any type, so let's give it a try
        if (
            self.args.return_type() is not None
            and self.args.return_type() != list[None]
            and self.input_type() is not None
            and self.input_type() != list[None]
        ):
            # Compare the origin types. The origin or `list[int]` is `list`
            origin_input_type = get_origin(self.input_type())
            origin_args_ret_type = get_origin(self.args.return_type())
            if origin_input_type != origin_args_ret_type:
                raise TypeError(f"We expect a {self.input_type()} as input but got {self.args.return_type()}")

            # Compare the subscripted types. The subscripted type of `list[int, float]` are `int, float`
            list_nested_input_type = get_args(self.input_type())
            list_nested_args_return_types = get_args(self.args.return_type())
            # Check that all the subscripted types of the arguments match at least one of
            # the subscripted types that this operator expects as input
            for nested_args_ret_type in list_nested_args_return_types:
                type_match = False
                for nested_input_type in list_nested_input_type:
                    if issubclass(nested_args_ret_type, nested_input_type):
                        type_match = True
                        break
                if not type_match:
                    raise TypeError(f"We expect {self.input_type()} as input but got {self.args.return_type()}")

    def get_value(self, contexts: list) -> Any:
        elements = self.args.get_value(contexts)

        # An example of elements=None is when the args is a list of elements
        # extracted from a getValue operation. If this getValue cannot find
        # anything for the provided path, then it returns None. In that case,
        # None means an empty list
        if elements is None:
            elements = []

        if not isinstance(elements, list):
            raise TypeError(f"Expected list but got {elements}")

        if len(elements) == 0:
            return self._zero_args_result()

        elem = elements[0]
        # If we have a single element, try to cast it to the type the operation
        # should return. For example, if the element is an int and the operation
        # returns a bool, this step will cast this int to a bool
        if len(elements) == 1:
            return self.return_type().__call__(elem)  # pylint: disable=unnecessary-dunder-call

        for arg_value in elements[1:]:
            elem = self._op(elem, arg_value)
        return elem

    @abc.abstractmethod
    def _op(self, lhs, rhs):
        pass

    def _zero_args_result(self):
        """The value returned when there are 0 arguments in the operator"""
        return self.return_type().__call__()  # pylint: disable=unnecessary-dunder-call


class BoolOp(BinaryOp):
    def input_type(self) -> type | None:
        return list[bool]

    def return_type(self) -> type | None:
        return bool


class And(BoolOp):
    def _op(self, lhs, rhs):
        return lhs and rhs

    def _zero_args_result(self):
        # This follows the default behaviour in Python when executing `all([])`
        return True


class Or(BoolOp):
    def _op(self, lhs, rhs):
        return lhs or rhs

    def _zero_args_result(self):
        # This follows the default behaviour in Python when executing `any([])`
        return False


class ArithOp(BinaryOp):
    def input_type(self) -> type | None:
        return list[Number]

    def return_type(self) -> type | None:
        return Number

    def _zero_args_result(self) -> Number:
        return 0


class Sum(ArithOp):
    def _op(self, lhs, rhs):
        return lhs + rhs


class Sub(ArithOp):
    def _op(self, lhs, rhs):
        return lhs - rhs


class Mul(ArithOp):
    def _op(self, lhs, rhs):
        return lhs * rhs


class Div(ArithOp):
    def _op(self, lhs, rhs):
        return lhs / rhs


class Comp(BinaryOp):
    def get_value(self, contexts: list) -> Any:
        list_arg_values = self.args.get_value(contexts)
        if len(list_arg_values) < 2:
            return True
        if len(list_arg_values) == 2:
            return self._op(list_arg_values[0], list_arg_values[1])
        raise ValueError("A comparison cannot have more than 2 operands")

    def input_type(self) -> type | None:
        return list[None]

    def return_type(self) -> type | None:
        return bool


class Equal(Comp):
    def _op(self, lhs, rhs):
        return lhs == rhs


class NotEqual(Comp):
    def _op(self, lhs, rhs):
        return lhs != rhs


class LessOrEqual(Comp):
    def _op(self, lhs, rhs):
        return lhs <= rhs


class GreaterOrEqual(Comp):
    def _op(self, lhs, rhs):
        return lhs >= rhs


class LessThan(Comp):
    def _op(self, lhs, rhs):
        return lhs < rhs


class GreaterThan(Comp):
    def _op(self, lhs, rhs):
        return lhs > rhs


class UnaryOp(Operator):
    def __init__(self, arg: Operator) -> None:
        self.arg = arg
        if self.arg.return_type() != self.input_type():
            raise TypeError(f"Expected an input type of {self.input_type()}, but got {self.arg.return_type()}")

    def get_value(self, contexts: list) -> Any:
        arg_value = self.arg.get_value(contexts)
        return self._op(arg_value)

    @abc.abstractmethod
    def _op(self, arg_value):
        pass


class Not(UnaryOp):
    def input_type(self) -> type | None:
        return bool

    def return_type(self) -> type | None:
        return bool

    def _op(self, arg_value):
        return not arg_value


class List(Operator):
    def __init__(self, list_op: list[Operator]) -> None:
        self.list_op = list_op

        # Get all the different return types, but ignore None, since this means
        # that the return type is not defined at "compile" time (depens on the input data)
        types_in_list = set(op.return_type() for op in self.list_op if op.return_type() is not None)
        if len(types_in_list) == 0:
            self.item_types = list[None]
        else:
            # For example, if `types_in_list={int, float}`, then
            # `self.item_types=list[int, float]`
            self.item_types = list[*list(types_in_list)]

    def get_value(self, contexts: list):
        return [op.get_value(contexts) for op in self.list_op]

    def input_type(self) -> type | None:
        return None

    def return_type(self) -> type | None:
        return self.item_types


class ForEach(Operator):
    def __init__(self, elements: Operator, op: Operator) -> None:
        self.elements = elements
        self.op = op

    def get_value(self, contexts: list):
        elements = self.elements.get_value(contexts)
        if elements is None:
            return []

        result_list = []
        for elem in elements:
            mapped_elem = self.op.get_value(contexts + [elem])
            result_list.append(mapped_elem)
        return result_list

    def input_type(self) -> type | None:
        return None

    def return_type(self) -> type | None:
        return list[self.op.return_type()]


class Contain(Operator):
    def __init__(self, elements: Operator, elem: Operator) -> None:
        self.elements = elements
        self.elem = elem

    def get_value(self, contexts: list):
        target_elem = self.elem.get_value(contexts)
        for elem in self.elements.get_value(contexts):
            if target_elem == elem:
                return True
        return False

    def input_type(self) -> type | None:
        return None

    def return_type(self) -> type | None:
        return bool


class Const(Operator):
    def __init__(self, value: Any) -> None:
        self.value = value

    def get_value(self, contexts: list):
        return self.value

    def input_type(self) -> type | None:
        return None

    def return_type(self) -> type | None:
        return type(self.value)


class GetValue(Operator):
    def __init__(self, path: list[str], context_id: int) -> None:
        self.path = path
        self.context_id = context_id

    def get_value(self, contexts: list):
        context = contexts[self.context_id]
        return self._get_value_from_json(context, self.path)

    def _get_value_from_json(self, data: Union[list, dict], path: list):
        if len(path) == 0 or path[0] == "":
            return data

        if isinstance(data, dict):
            key = path[0]
            if key in data:
                return self._get_value_from_json(data[key], path[1:])
        elif isinstance(data, list):
            key = int(path[0])
            if 0 <= key < len(data):
                return self._get_value_from_json(data[key], path[1:])
        else:
            raise RuntimeError(f"Expected list or dict, but got {data}")

        return None

    def input_type(self) -> type | None:
        return None

    def return_type(self) -> type | None:
        return None
