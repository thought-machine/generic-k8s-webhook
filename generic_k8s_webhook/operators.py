import abc
import inspect
import re
import sys
from typing import Union, Any


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

        # A None return type for the arguments means that we have an empty list of arguments
        if self.return_type() is not None and self.input_type() != self.args.return_type():
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
            self.return_type = None
        else:
            self.return_type = list[types_in_list.pop()]

    def get_value(self, contexts: list):
        return [op.get_value(contexts) for op in self.list_op]

    def input_type(self) -> type:
        return None

    def return_type(self) -> type:
        return list[self.return_type]


class ForEach(Operator):
    def __init__(self, op_inputs: Any, path_op: str) -> None:
        if "elements" not in op_inputs:
            raise ValueError(f"The forEach placed in {path_op} required the argument 'elements'")
        self.elements = parse_operator(op_inputs["elements"], f"{path_op}.elements")

        if "op" not in op_inputs:
            raise ValueError(f"The forEach placed in {path_op} required the argument 'op'")
        self.op = parse_operator(op_inputs["op"], f"{path_op}.op")

    def get_value(self, contexts: list):
        result_list = []
        for elem in self.elements.get_value():
            mapped_elem = self.op.get_value(contexts + [elem])
            result_list.append(mapped_elem)
        return result_list

    def input_type(self) -> type:
        return None

    def return_type(self) -> type:
        return list[self.op.return_type()]


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


class Path(Operator):
    NAME = "path"

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
        if isinstance(data, dict):
            return self._get_value_from_json(data[path[0]], path[1:])
        elif isinstance(data, list):
            return self._get_value_from_json(data[int(path[0]), path[1:]])
        else:
            return data

    def input_type(self) -> type:
        return None

    def return_type(self) -> type:
        return None


# Magic dictionary that contains all the operators defined in this file
dict_operators = {
    obj.NAME: obj
    for _, obj in inspect.getmembers(sys.modules[__name__])
    if isinstance(obj, type) and issubclass(obj, Operator) and hasattr(obj, "NAME")
}

def parse_operator(op_spec: dict, path_op: str="") -> Operator:
    if len(op_spec) != 1:
        raise ValueError(f"Expected exactly one key under {path_op}")
    op_name, op_spec = op_spec.popitem()
    if op_name not in dict_operators:
        raise ValueError(f"The operator {op_name} from {path_op} is not defined")
    op_class = dict_operators[op_name]
    op = op_class(op_spec, f"{path_op}.{op_name}")

    return op

# class BaseOp(abc.ABC):
#     @abc.abstractclassmethod
#     def operate(self, values: list) -> bool:
#         pass


# class Any(BaseOp):
#     NAME = "any"

#     @classmethod
#     def operate(self, values: list) -> bool:
#         return any(values)


# class All(BaseOp):
#     NAME = "all"

#     @classmethod
#     def operate(self, values: list) -> bool:
#         return all(values)


# class And(BaseOp):
#     NAME = "and"

#     @classmethod
#     def operate(self, values: list) -> bool:
#         return all(values)


# class Or(BaseOp):
#     NAME = "or"

#     @classmethod
#     def operate(self, values: list) -> bool:
#         return any(values)
