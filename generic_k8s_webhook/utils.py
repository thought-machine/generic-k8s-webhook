import re
from typing import Any


def must_get(d: dict, key: Any, err_msg: str) -> Any:
    if key not in d:
        raise ValueError(err_msg)
    return d[key]


def must_pop(d: dict, key: Any, err_msg: str) -> Any:
    if key not in d:
        raise ValueError(err_msg)
    return d.pop(key)


def convert_dot_string_path_to_list(dot_string_path: str) -> list[str]:
    # Split by '.', but not by '\.'
    path = re.split(r"(?<!\\)\.", dot_string_path)
    # Convert the '\.' to '.'
    path = [elem.replace("\\.", ".") for elem in path]
    return path
