from typing import Any


def must_get(d: dict, key: Any, err_msg: str) -> Any:
    if key not in d:
        raise ValueError(err_msg)
    return d[key]


def must_pop(d: dict, key: Any, err_msg: str) -> Any:
    if key not in d:
        raise ValueError(err_msg)
    return d.pop(key)
