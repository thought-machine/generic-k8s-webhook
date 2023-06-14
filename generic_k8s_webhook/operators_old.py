import abc
import inspect
import sys
from typing import Union


class Operator(abc.ABC):
    @abc.abstractmethod
    def return_type(self) -> type:
        pass


class BinaryOp(Operator):
    pass


class AndOp(Operator):
    NAME = "and"
    INPUT_TYPE = list[bool]
    RETURN_TYPE = bool

    def __init__(self, op_inputs: dict, path_op: str) -> None:
        self.args = parse_operator(op_inputs, path_op)
        if self.INPUT_TYPE != self.args.return_type():
            raise RuntimeError(f"In {path_op} we expect {self.INPUT_TYPE} as input but got {self.args.return_type()}")


class List(Operator):
    NAME = "list"

    def __init__(self, op_spec: list, path_op: str) -> None:
        self.list_op = []
        for i, op in enumerate(op_spec):
            self.list_op = parse_operator(op, f"{path_op}.{i}")

        self.return_type = None
        if len(self.list_op) > 0:
            self.return_type = type(self.list_op[0])
        for op in self.list_op:
            if op.return_type() != self.return_type:
                raise RuntimeError(f"Non homogeneous return type in {path_op}")

    def return_type(self) -> type:
        return list[self.return_type]



# Magic dictionary that contains all the operators defined in this file
dict_operators = {
    obj.NAME: obj
    for _, obj in inspect.getmembers(sys.modules[__name__])
    if issubclass(obj, Operator)
}

def parse_operator(op_spec: Union[dict, list], path_op: str="") -> Operator:
    if isinstance(op_spec, list):
        op = List(op_spec, path_op)

    elif isinstance(op_spec, dict):
        if len(op_spec) != 1:
            raise ValueError(f"Expected exactly one key under {path_op}")
        op_name, op_spec = op_spec.popitem()
        if op_name not in dict_operators:
            raise ValueError(f"The operator {op_name} from {path_op} is not defined")
        op_class = dict_operators[op_name]
        op = op_class(op_spec, f"{path_op}.{op_name}")

    else:
        raise ValueError(f"Expecting list or dict, but got {op_spec} in {path_op}")

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
