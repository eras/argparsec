# argparsec

Typed parser combinators for lists of argument tokens. Python 3.12 or newer, with no runtime dependencies.

## Example

```python
import argparsec as p

grammar = p.Remaining(p.Keyword("limit", p.Int()))
result = grammar.parse(["limit", "80"])

if isinstance(result, p.ParseOK):
    print(result.value)      # 80
    print(result.processed)  # 2
else:
    assert isinstance(result, p.ParseFail)
    print(result.message)
```

Input is already tokenized. Tokenization, quoting, transport normalization, and command execution belong to the caller. Individual numeric parsers require complete tokens: `"123abc"` is not an integer.

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

## Development

```sh
python -m pip install -e '.[dev]'
python -m unittest discover
mypy -p argparsec -p tests
black --check src tests
python -m build
```

Both `import argparsec as p` and `import argparsec.parser as p` expose the parser API. The limited `argparsec.utils` module supports the implementation and is not part of the root API.

## Origin

Extracted from TeslaBot with filtered source and test history dating back to March 2022. See [history/README.md](history/README.md) for the source revision, filtering rules, and commit mapping. The original MIT attribution is retained in [LICENSE.MIT](LICENSE.MIT).
