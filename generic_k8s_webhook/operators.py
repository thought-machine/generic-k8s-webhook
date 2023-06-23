import abc
from numbers import Number
from typing import Any, Union, get_args, get_origin


def _to_number(element) -> int | float:
    try:
        return int(element)
    except (ValueError, TypeError):
        pass
    try:
        return float(element)
    except (ValueError, TypeError):
        pass

    raise RuntimeError(f"Cannot convert {element} to number")


# Make Number callable, so it can convert, for example, a string into an int or float
Number.__call__ = _to_number


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
            and self.input_type() != list[None]
            and self.args.return_type() != list[None]
        ):
            # The return type of the arguments must be a list
            if get_origin(self.args.return_type()) != list:
                raise TypeError(f"We expect a list as input but got {self.args.return_type()}")
            # Compare the subscripted types
            nested_input_type = get_args(self.input_type())
            nested_args_return_type = get_args(self.args.return_type())
            if not issubclass(nested_args_return_type[0], nested_input_type[0]):
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
            return self._no_op_result()

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

    @abc.abstractmethod
    def _no_op_result(self):
        pass


class And(BinaryOp):
    def input_type(self) -> type | None:
        return list[bool]

    def return_type(self) -> type | None:
        return bool

    def _op(self, lhs, rhs):
        return lhs and rhs

    def _no_op_result(self):
        return True


class Or(BinaryOp):
    def input_type(self) -> type | None:
        return list[bool]

    def return_type(self) -> type | None:
        return bool

    def _op(self, lhs, rhs):
        return lhs or rhs

    def _no_op_result(self):
        return True


class Equal(BinaryOp):
    def get_value(self, contexts: list) -> Any:
        list_arg_values = self.args.get_value(contexts)
        if len(list_arg_values) < 2:
            return True
        elem_golden = list_arg_values[0]
        for elem in list_arg_values[1:]:
            if elem != elem_golden:
                return False
        return True

    def input_type(self) -> type | None:
        return list[None]

    def return_type(self) -> type | None:
        return bool

    def _op(self, lhs, rhs):
        pass  # unused

    def _no_op_result(self):
        pass  # unused


class Sum(BinaryOp):
    def input_type(self) -> type | None:
        return list[Number]

    def return_type(self) -> type | None:
        return Number

    def _op(self, lhs, rhs):
        return lhs + rhs

    def _no_op_result(self):
        return 0


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
        if len(types_in_list) > 1:
            raise TypeError("Non homogeneous return type")
        if len(types_in_list) == 0:
            self.item_type = None
        else:
            self.item_type = types_in_list.pop()

    def get_value(self, contexts: list):
        return [op.get_value(contexts) for op in self.list_op]

    def input_type(self) -> type | None:
        return None

    def return_type(self) -> type | None:
        return list[self.item_type]


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
        return self._get_value_from_json(context, self.path[1:])

    def _get_value_from_json(self, data: Union[list, dict], path: list):
        if len(path) == 0 or path[0] == "":
            return data

        if isinstance(data, dict):
            key = path[0]
        elif isinstance(data, list):
            key = int(path[0])
        else:
            raise RuntimeError(f"Expected list or dict, but got {data}")

        if key in data:
            return self._get_value_from_json(data[key], path[1:])
        return None

    def input_type(self) -> type | None:
        return None

    def return_type(self) -> type | None:
        return None
