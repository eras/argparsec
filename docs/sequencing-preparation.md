# Deterministic sequencing and prepared invocation

## Typed forward-only sequencing

`Then(left, right)` returns `Parser[tuple[A, B]]` for children returning `A` and `B`. It calls the left child once with the input, then calls the right child once with the unconsumed suffix. A left failure skips the right child. A right failure retains its diagnostic with the left consumption added to its offset. Success consumption is the sum of both children's consumption. Zero-consumption successes are valid.

```python
import argparsec as p

grammar = p.Then(p.Keyword("in", p.Int()), p.RestAsStr())
assert grammar.parse(["in", "10", "buy", "milk"]) == p.ParseOK((10, "buy milk"), 4)
```

Choose `Then` for self-delimiting headers followed by tails. It does not shrink a greedy left parse to make the right child succeed: `Then(RestAsStr(), Int())` fails because the left child consumes all tokens. Use `Adjacent` when the grammar needs token-boundary search. `Adjacent`, `IfThen`, and homogeneous `Seq` retain their own contracts. Each `Then` invokes each reached child once, but children can themselves search or repeat parsing, and suffix slicing still copies token lists.

Generated help traverses both children, including structural tokens whose values are discarded. To keep only one value, use `Map` over `Then`:

```python
def keep_right(pair: tuple[str, int]) -> int:
    """Discard the structural token while retaining the parsed integer."""
    return pair[1]


value = p.Map(keep_right, p.Then(p.CaptureFixedStr("value"), p.Int()))
```

Use index `0` for the equivalent keep-left operation. For a fixed leading keyword, `Keyword("value", Int())` already provides forward-only consumption and returns only the integer.

## Validate before execution

`Function[Context, Parsed]` connects the argument parser and asynchronous callback statically. Its preparation APIs are:

- `prepared_parser() -> Parser[Prepared[Context]]`: parse argument tokens, preserving successful consumption and failure messages/offsets. The Function name and description are not included in this grammar; compose `Keyword` and `Meta` as appropriate.
- `prepare(invocation) -> Prepared[Context]`: parse `invocation.args` once, returning deferred execution or raising `CommandParseError` with the same diagnostic and marked original tokens as `invoke`. The invocation name is used only for diagnostics, not checked against the Function name.
- `await prepared.invoke(context)`: call the captured handler with the captured typed value, without parsing or validating again. Handler exceptions propagate unchanged. Each awaited invocation executes again; this is not a single-use transaction.

Preparation runs parsing and validation, including `Map` functions, but never calls the execution callback. Validators must be safe for speculative parsing when used inside alternatives or boundary-search combinators. Prepared values and callback references are captured on successful preparation; values are not deep-copied. Applications own mutation, authorization, context lifetime, and any execute-once policy. A parser returned by `prepared_parser()` retains the argument parser supplied when that parser view is created; the current handler is captured when parsing succeeds.

```python
import argparsec.commands as c


async def record(context: list[int], value: int) -> None:
    """Store a validated integer in application-owned state."""
    context.append(value)


function = c.Function("limit", "Record a limit", p.Remaining(p.Int()), record)
prepared = function.prepare(c.Invocation("limit", ["80"]))
# Later, in asynchronous application code:
# await prepared.invoke(context)
```

## Complete alternatives, including shared command names

Parsers accept prefixes unless wrapped in `Remaining`. Require completeness **inside each alternative**, before `OneOf` selects a successful branch:

```python
async def record_pair(context: list[int], value: tuple[int, bool]) -> None:
    """Store the integer when the parsed switch is enabled."""
    if value[1]:
        context.append(value[0])


short = c.Function("limit", "One argument", p.Int(), record)
long = c.Function("limit", "Two arguments", p.Then(p.Int(), p.Bool()), record_pair)
grammar = p.OneOf(
    p.Keyword("limit", p.Remaining(short.prepared_parser())),
    p.Keyword("limit", p.Remaining(long.prepared_parser())),
)
result = grammar.parse(["limit", "80", "on"])
assert isinstance(result, p.ParseOK)
# Only the long branch's handler executes when explicitly awaited:
# await result.value.invoke(context)
```

Wrapping only the entire `OneOf` in `Remaining` is insufficient: its first prefix success prevents trying a later complete alternative. `OneOf` retains first-success ordering and its own failure aggregation rules. Prepared parsers expose argument syntax through the help renderer's transparent `Map` traversal without running validation or execution.

`Commands.parser()` defers argument validation until execution, and registry dispatch executes all matching registrations. Use explicit prepared-parser alternatives when only one fully validated branch should execute; these APIs do not change registry dispatch semantics.

## Consumer migration checklist

For HomeMau and TeslaBot integrations:

1. Update the argparsec dependency to the published Git revision and reinstall or refresh the environment using the application's dependency manager.
2. Replace local forward-only `Adjacent` subclasses with `Then`; preserve application mappings and result shapes. Keep `Adjacent` where searching boundaries is intentional.
3. Replace closures calling `Function.fn[0]` with `Function.prepared_parser()`, and execute the selected value with `await prepared.invoke(context)`. Use `Function.prepare(invocation)` for direct exception-based preparation.
4. Require complete validation inside each alternative. Compose command names explicitly; prepared parsers consume arguments only. Add metadata for descriptions and examples as needed.
5. Keep original-text capture, command admission, persistence, authorization, scheduling, and transport handling in the application. `RestAsStr` joins tokens; it does not preserve original spacing.
6. Run application typing checks, help snapshots, invalid-input/offset tests, same-name branch-selection tests, no-execution-on-failure tests, and long-tail parser-call-count regressions. Confirm preparation and help never run execution callbacks and invocation never reparses.
