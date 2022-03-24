from typing import Optional, TypeVar, Callable

T = TypeVar("T")

U = TypeVar("U")

def assert_some(x: Optional[T], message: Optional[str] = None) -> T:
    if message is not None:
        assert x is not None, message
    else:
        assert x is not None
    return x

def coalesce(*xs: Optional[T]) -> T:
    """Return the first non-None value from the list; there must be at least one"""
    for x in xs:
        if x is not None:
            return x
    assert False, "Expected at least one element to be non-None"

def map_optional(x: Optional[T], fn: Callable[[T], U]) -> Optional[U]:
    if x is None:
        return None
    else:
        return fn(x)
