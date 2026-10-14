import datetime

from typing import TypeVar

from collections.abc import Callable

T = TypeVar("T")

U = TypeVar("U")

def assert_some(x: T | None, message: str | None = None) -> T:
    if message is not None:
        assert x is not None, message
    else:
        assert x is not None
    return x

def round_to_next_second(time: datetime.datetime) -> datetime.datetime:
    return time + datetime.timedelta(microseconds=1000000-time.microsecond)

def coalesce(*xs: T | None) -> T:
    """Return the first non-None value from the list; there must be at least one"""
    for x in xs:
        if x is not None:
            return x
    assert False, "Expected at least one element to be non-None"

def map_optional(x: T | None, fn: Callable[[T], U]) -> U | None:
    if x is None:
        return None
    else:
        return fn(x)
