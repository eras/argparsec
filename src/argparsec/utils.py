"""Internal support for parser values and datetime arithmetic."""

import datetime

from collections.abc import Callable


def assert_some[T](x: T | None, message: str | None = None) -> T:
    """Return a non-None value, asserting with an optional diagnostic otherwise."""
    if message is not None:
        assert x is not None, message
    else:
        assert x is not None
    return x


def round_to_next_second(time: datetime.datetime) -> datetime.datetime:
    """Advance strictly to the next whole second, preserving timezone information."""
    return time + datetime.timedelta(microseconds=1000000 - time.microsecond)


def coalesce[T](*xs: T | None) -> T:
    """Return the first non-None value from the list; there must be at least one"""
    for x in xs:
        if x is not None:
            return x
    assert False, "Expected at least one element to be non-None"


def map_optional[T, U](x: T | None, fn: Callable[[T], U]) -> U | None:
    """Transform a present value without calling the function for None."""
    if x is None:
        return None
    else:
        return fn(x)
