# argparsec

Typed parser combinators and optional asynchronous command dispatch for lists of argument tokens. Python 3.12 or newer, with no runtime dependencies.

## Example

```python
import typing

import argparsec as p

grammar = p.Remaining(p.Keyword("limit", p.Int()))
result = grammar.parse(["limit", "80"])

match result:
    case p.ParseOK(value=value, processed=processed):
        print(value)      # 80
        print(processed)  # 2
    case p.ParseFail(message=message):
        print(message)
    case _:
        typing.assert_never(result)
```

`ParseResult[T]` is the union alias `ParseOK[T] | ParseFail[T]`. The `assert_never` fallback lets mypy check that every result variant is handled. Alternatively, enable mypy's `exhaustive-match` error code and omit the fallback. Use the concrete variants for `isinstance` checks; `ParseResult` is a type alias, not a class, and cannot be subclassed or used with `isinstance`.

Parser input is already tokenized. Tokenization, quoting, and transport normalization belong to the caller, with a simple tokenizer available in the optional command module below. Individual numeric parsers require complete tokens: `"123abc"` is not an integer.

## Parsing Contract

- `Parser[T].parse(args)` returns `ParseOK[T]` or `ParseFail[T]`.
- Success records a value and the number of tokens consumed. Parsers can accept a prefix; wrap them in `Remaining` to require complete consumption.
- Failure records a message and a zero-based token offset relative to the supplied input. An offset equal to the input length points to end of input.
- `OneOf` tries alternatives in order, including on empty input, and returns the first success. A zero-consumption success also wins immediately.
- `Optional` converts any wrapped parse failure into a zero-consumption success with `None`. Use `ValidOrMissing` to reject present but invalid input.
- `List` accepts zero or more items. It stops before a failed item and rejects successful items that consume nothing on nonempty input.
- `Adjacent` searches candidate token boundaries, with configurable left or right priority; it is not just sequential composition.
- `Separated` requires a nonempty, complete sequence. It first prefers an interpretation of the whole input as one item, then searches grammar-valid separator boundaries.
- Speculative parsing can invoke parsers and mapping functions repeatedly. Keep them free of irreversible side effects; construct callbacks during parsing and execute them only after validation.

The package also includes date/time, unit-suffix, enum, boolean, and Slack-link normalization parsers. Date/time defaults use the local clock; constructors accept reference dates or times for deterministic parsing. `Interval` requires at least one minute. `TimeOrDateTime` rejects explicit datetimes in the past. `Url` normalizes Slack-style angle brackets and escaped ampersands without changing input tokens; it is not a URL validator.

## Command Dispatch

`argparsec.commands` provides a registry, typed asynchronous callbacks, invocation objects, help text, and marked argument errors. It does not own an application context, transport, authorization policy, or event loop.

```python
import asyncio

import argparsec as p
import argparsec.commands as c


async def record_limit(context: list[int], limit: int) -> None:
    """Record a parsed limit in application-owned state."""
    context.append(limit)


async def main() -> None:
    """Register and invoke a command with an explicit context."""
    commands = c.Commands[list[int]]()
    commands.register(c.Function("limit", "Record a limit", p.Remaining(p.Int()), record_limit))
    context: list[int] = []
    await commands.invoke(context, c.Invocation.parse("limit 80"))
    assert context == [80]


asyncio.run(main())
```

- `Invocation(name, args)` accepts an already-tokenized command. `Invocation.parse(text)` is a convenience tokenizer: it splits literal spaces, discards empty fields, and strips everything from the first `#`. It does not implement quoting or shell syntax. Empty input raises `InvocationEmptyError`.
- `Function.invoke` parses arguments before calling its asynchronous handler. Failures raise `CommandParseError` with the original diagnostic and marked tokens. Callback exceptions propagate normally. Wrap the argument parser in `Remaining` if trailing arguments must fail.
- Registry lookup and execution are case-insensitive. Duplicate names are allowed; all matching handlers execute sequentially in registration order. Direct invocation of an unknown name does nothing.
- `Commands.parser()` is a live view of the registry. It returns a parser producing an awaitable callback for a recognized name. Parsing does not execute the handler or validate its arguments; validation occurs when the returned callback is awaited.
- The boolean `Function.parse` and `Commands.parse` methods are not reliable argument validators: the former checks only whether the parser result is non-None, and the latter checks exact-name membership after asserting case-insensitive membership. Use a parser's `ParseOK`/`ParseFail` result or `Function.invoke` instead.
- The module provides detailed DEBUG command-token logging through Python's standard logging system. Applications configure handlers; the library does not install them.

## Development

```sh
python -m pip install -e '.[dev]'
python -m unittest discover
mypy -p argparsec -p tests
black --check src tests
python -m build
```

Both `import argparsec as p` and `import argparsec.parser as p` expose the parser API. Dispatch is a separate opt-in module, `argparsec.commands`. The limited `argparsec.utils` module supports the implementation and is not part of the root API.

## Origin

Extracted from TeslaBot with filtered source and test history dating back to March 2022. See [history/README.md](history/README.md) for the source revision, filtering rules, and commit mapping. The original MIT attribution is retained in [LICENSE.MIT](LICENSE.MIT).
