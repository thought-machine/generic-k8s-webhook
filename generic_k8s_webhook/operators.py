import abc
import inspect
import re
import sys
from typing import Union, Any, get_origin, get_args
from numbers import Number

import generic_k8s_webhook.utils as utils


class Operator(abc.ABC):
    @abc.abstractmethod
    def __init__(self, op_inputs: Any, path_op: str) -> None:
        pass

    @abc.abstractmethod
    def input_type(self) -> type:
        pass

    @abc.abstractmethod
    def return_type(self) -> type:
        pass

    @abc.abstractmethod
    def get_value(self, contexts: list):
        pass


# It's the base class for operators like and, or, sum, etc.
# Even if it's called BinaryOp, it supports a list of arguments of any size
# For example: and(true, false, true, true) -> false
class BinaryOp(Operator):
    def __init__(self, op_inputs: Union[dict, list], path_op: str) -> None:
        if isinstance(op_inputs, list):
            self.args = List(op_inputs, path_op)
        elif isinstance(op_inputs, dict):
            self.args = parse_operator(op_inputs, path_op)
        else:
            raise ValueError(f"Expected dict or list as input, but got {op_inputs}")

        # A None return type of the arguments means that this type is not defined at "compile" time
        # A list[None] for the input_type means that this operation can potentially consume any type
        if self.args.return_type() is not None and self.input_type() != list[None]:
            # The return type of the arguments must be a list
            if get_origin(self.args.return_type()) != list:
                raise ValueError(f"In {path_op} we expect a list as input but got {self.args.return_type()}")
            # Compare the subscripted types
            nested_input_type = get_args(self.input_type())
            nested_args_return_type = get_args(self.args.return_type())
            if not issubclass(nested_args_return_type[0], nested_input_type[0]):
                raise RuntimeError(f"In {path_op} we expect {self.input_type()} as input but got {self.args.return_type()}")

    def get_value(self, contexts: list) -> Any:
        elem = self._neutral_elem()
        for arg_value in self.args.get_value(contexts):
            elem = self._op(elem, arg_value)
        return elem

    @abc.abstractmethod
    def _op(self, lhs, rhs):
        pass

    @abc.abstractmethod
    def _neutral_elem(self):
        pass


class And(BinaryOp):
    NAME = "and"

    def input_type(self) -> type:
        return list[bool]

    def return_type(self) -> type:
        bool

    def _op(self, lhs, rhs):
        return lhs and rhs

    def _neutral_elem(self):
        return True


class Or(BinaryOp):
    NAME = "or"

    def input_type(self) -> type:
        return list[bool]

    def return_type(self) -> type:
        bool

    def _op(self, lhs, rhs):
        return lhs or rhs

    def _neutral_elem(self):
        return False
    

class Equal(BinaryOp):
    NAME = "equal"

    def get_value(self, contexts: list) -> Any:
        list_arg_values = self.args.get_value(contexts)
        if len(list_arg_values) < 2:
            return True
        elem_golden = list_arg_values[0]
        for elem in list_arg_values[1:]:
            if elem != elem_golden:
                return False
        return True

    def input_type(self) -> type:
        return list[None]

    def return_type(self) -> type:
        bool

    def _op(self, lhs, rhs):
        pass  # unused

    def _neutral_elem(self):
        pass  # unused


class Sum(BinaryOp):
    NAME = "sum"

    def input_type(self) -> type:
        return list[Number]

    def return_type(self) -> type:
        Number

    def _op(self, lhs, rhs):
        return lhs + rhs

    def _neutral_elem(self):
        return 0


class UnaryOp(Operator):
    def __init__(self, op_inputs: Any, path_op: str) -> None:
        self.arg = parse_operator(op_inputs, path_op)
        if self.arg.return_type() != self.input_type():
            raise ValueError(f"In {path_op}, expected an input type of {self.input_type()}, but got {self.arg.return_type()}")

    def get_value(self, contexts: list) -> Any:
        arg_value = self.arg.get_value(contexts)
        return self._op(arg_value)

    @abc.abstractmethod
    def _op(self, arg_value):
        pass

class Not(UnaryOp):
    NAME = "not"

    def input_type(self) -> type:
        return bool

    def return_type(self) -> type:
        return bool

    def _op(self, arg_value):
        return not arg_value

class List(Operator):
    NAME = "list"

    def __init__(self, op_spec: list, path_op: str) -> None:
        self.list_op = []
        for i, op in enumerate(op_spec):
            parsed_op = parse_operator(op, f"{path_op}.{i}")
            self.list_op.append(parsed_op)

        # Get all the different return types, but ignore None, since this means
        # that the return type is not defined at "compile" time (depens on the input data)
        types_in_list = set(
            op.return_type()
            for op in self.list_op
            if op.return_type() is not None
        )
        if len(types_in_list) > 1:
            raise RuntimeError(f"Non homogeneous return type in {path_op}")
        if len(types_in_list) == 0:
            self.item_type = None
        else:
            self.item_type = types_in_list.pop()

    def get_value(self, contexts: list):
        return [op.get_value(contexts) for op in self.list_op]

    def input_type(self) -> type:
        return None

    def return_type(self) -> type:
        return list[self.item_type]


class ForEach(Operator):
    NAME = "forEach"

    def __init__(self, op_inputs: Any, path_op: str) -> None:
        if "elements" not in op_inputs:
            raise ValueError(f"The forEach placed in {path_op} required the argument 'elements'")
        self.elements = parse_operator(op_inputs["elements"], f"{path_op}.elements")

        if "op" not in op_inputs:
            raise ValueError(f"The forEach placed in {path_op} required the argument 'op'")
        self.op = parse_operator(op_inputs["op"], f"{path_op}.op")

    def get_value(self, contexts: list):
        result_list = []
        for elem in self.elements.get_value(contexts):
            mapped_elem = self.op.get_value(contexts + [elem])
            result_list.append(mapped_elem)
        return result_list

    def input_type(self) -> type:
        return None

    def return_type(self) -> type:
        return list[self.op.return_type()]


class Contain(Operator):
    NAME = "contain"

    def __init__(self, op_inputs: Any, path_op: str) -> None:
        self.elements = utils.must_get(op_inputs, "elements",
                                       f"The forEach placed in {path_op} required the argument 'elements'")
        self.elem = utils.must_get(op_inputs, "value",
                                   f"The forEach placed in {path_op} required the argument 'value'")


    def get_value(self, contexts: list):
        target_elem = self.elem.get_value(contexts)
        for elem in self.elements.get_value(contexts):
            if target_elem == elem:
                return True
        return False

    def input_type(self) -> type:
        return None

    def return_type(self) -> type:
        return bool


class Const(Operator):
    NAME = "const"

    def __init__(self, op_inputs: Any, path_op: str) -> None:
        self.value = op_inputs

    def get_value(self, contexts: list):
        return self.value

    def input_type(self) -> type:
        return None

    def return_type(self) -> type:
        return type(self.value)


class GetValue(Operator):
    NAME = "getValue"

    def __init__(self, op_inputs: str, path_op: str) -> None:
        if not isinstance(op_inputs, str):
            raise ValueError(f"Expected to find str but got {op_inputs} in {path_op}")
        # Split by '.', but not by '\.'
        self.path = re.split(r"(?<!\\)\.", op_inputs)
        # Convert the '\.' to '.'
        self.path = [elem.replace("\\.", ".") for elem in self.path]

        # Get the id of the context that it will use
        if self.path[0] == "":
            self.context_id = -1
        elif self.path[0] == "$":
            self.context_id = 0
        else:
            raise ValueError(f"Invalid {self.path[0]} in {path_op}")

    def get_value(self, contexts: list):
        context = contexts[self.context_id]
        return self._get_value_from_json(context, self.path[1:])

    def _get_value_from_json(self, data: Union[list, dict], path: list):
        if len(path) == 0 or path[0] == "":
            return data

        if isinstance(data, dict):
            return self._get_value_from_json(data[path[0]], path[1:])
        elif isinstance(data, list):
            return self._get_value_from_json(data[int(path[0])], path[1:])
        else:
            raise RuntimeError(f"Expected list or dict, but got {data}")

    def input_type(self) -> type:
        return None

    def return_type(self) -> type:
        return None


# Magic dictionary that contains all the operators defined in this file
DICT_OPERATORS = {}
for _, obj in inspect.getmembers(sys.modules[__name__]):
    if isinstance(obj, type) and issubclass(obj, Operator) and hasattr(obj, "NAME"):
        if obj.NAME in DICT_OPERATORS:
            raise RuntimeError(f"Duplicated operator {obj.NAME}")
        DICT_OPERATORS[obj.NAME] = obj


def parse_operator(op_spec: dict, path_op: str="") -> Operator:
    if len(op_spec) != 1:
        raise ValueError(f"Expected exactly one key under {path_op}")
    op_name, op_spec = op_spec.popitem()
    if op_name not in DICT_OPERATORS:
        raise ValueError(f"The operator {op_name} from {path_op} is not defined")
    op_class = DICT_OPERATORS[op_name]
    op = op_class(op_spec, f"{path_op}.{op_name}")

    return op
