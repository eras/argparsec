"""Verify deterministic typed composition and parse-once command preparation."""

import typing
import unittest
import dataclasses

import argparsec as p
import argparsec.commands as c


class Counting[T](p.Parser[T]):
    """Record every supplied token list before delegating to a typed parser."""

    def __init__(self, parser: p.Parser[T]) -> None:
        """Keep the parser and an independent invocation log."""
        self.parser = parser
        self.calls: list[list[str]] = []

    def parse(self, args: list[str]) -> p.ParseResult[T]:
        """Snapshot input without changing the wrapped parse result."""
        self.calls.append(args[:])
        return self.parser.parse(args)


class TestThen(unittest.TestCase):
    """Check single-pass sequencing separately from boundary-search combinators."""

    def test_typed_prefix_success(self) -> None:
        """Preserve heterogeneous values and let the caller require completeness."""
        left = Counting(p.Int())
        right = Counting(p.Bool())
        grammar = p.Then(left, right)
        typing.assert_type(grammar, p.Then[int, bool])
        args = ["12", "on", "extra"]
        self.assertEqual(grammar.parse(args), p.ParseOK((12, True), 2))
        self.assertEqual(left.calls, [args])
        self.assertEqual(right.calls, [["on", "extra"]])
        self.assertEqual(args, ["12", "on", "extra"])
        self.assertEqual(
            p.Remaining(grammar).parse(args),
            p.ParseFail("Extraneous input after command", 2),
        )

    def test_left_failure_skips_right(self) -> None:
        """Keep a nested left diagnostic and avoid evaluating the right child."""
        left = Counting(p.Keyword("value", p.Int()))
        right = Counting(p.Bool())
        args = ["value", "bad", "on"]
        expected = left.parser.parse(args)
        self.assertEqual(p.Then(left, right).parse(args), expected)
        self.assertEqual(left.calls, [args])
        self.assertEqual(right.calls, [])

    def test_right_failure_offsets_include_both_children(self) -> None:
        """Add left consumption to nested right failure and end-of-input offsets."""
        for args in (["12", "value", "bad"], ["12", "value"]):
            with self.subTest(args=args):
                left = Counting(p.Int())
                right = Counting(p.Keyword("value", p.Int()))
                expected = right.parser.parse(args[1:])
                assert isinstance(expected, p.ParseFail)
                self.assertEqual(
                    p.Then(left, right).parse(args), expected.forward(processed=1)
                )
                self.assertEqual(left.calls, [args])
                self.assertEqual(right.calls, [args[1:]])

    def test_zero_consumption_children(self) -> None:
        """Accept empty and zero-width successes without looping or skipping children."""
        left = Counting(p.Optional(p.Int()))
        right = Counting(p.Concat())
        grammar = p.Then(left, right)
        self.assertEqual(grammar.parse([]), p.ParseOK((None, ""), 0))
        self.assertEqual(grammar.parse(["tail"]), p.ParseOK((None, "tail"), 1))
        self.assertEqual(left.calls, [[], ["tail"]])
        self.assertEqual(right.calls, [[], ["tail"]])

    def test_greedy_left_is_not_retried(self) -> None:
        """A tail-consuming left child leaves no tokens for the right child."""
        left = Counting(p.RestAsStr())
        right = Counting(p.Int())
        result = p.Then(left, right).parse(["text", "12"])
        self.assertEqual(result, p.ParseFail("No argument provided", 2))
        self.assertEqual(left.calls, [["text", "12"]])
        self.assertEqual(right.calls, [[]])

    def test_nested_long_tail_has_bounded_child_calls(self) -> None:
        """Header depth and tail size must not cause prefix-search amplification."""
        first = Counting(p.CaptureFixedStr("remind"))
        second = Counting(p.Int())
        tail = Counting(p.RestAsStr())
        grammar = p.Then(p.Then(first, second), tail)
        for size in (1, 1000, 4000):
            args = ["remind", "12"] + ["word"] * size
            result = grammar.parse(args)
            self.assertEqual(
                result, p.ParseOK((("remind", 12), " ".join(args[2:])), len(args))
            )
        self.assertEqual([len(x.calls) for x in (first, second, tail)], [3, 3, 3])

    def test_help_and_discovery_walk_children_without_parsing(self) -> None:
        """Render executable sequence structure without evaluating mapping callbacks."""

        def forbidden(value: int) -> int:
            """Detect accidental validation during help traversal."""
            raise AssertionError("validation ran")

        grammar = p.Then(p.CaptureFixedStr("limit"), p.Map(forbidden, p.Int()))
        document = p.Help[None]().document(grammar, None)
        self.assertEqual(document.command_names(), {"limit"})
        self.assertIn("limit 123", document.render())
        self.assertEqual(
            p.render_help(grammar),
            p.render_help(p.Adjacent(p.CaptureFixedStr("limit"), p.Int())),
        )


class TestPreparation(unittest.IsolatedAsyncioTestCase):
    """Validate command arguments before any execution while keeping typed context."""

    async def test_prepare_parses_once_and_reuses_value(self) -> None:
        """Preparation captures a handler and value, not mutable invocation tokens."""
        parser = Counting(p.Int())

        async def record(context: list[int], value: int) -> None:
            """Record each explicit execution with its supplied context."""
            context.append(value)

        function = c.Function("limit", "", parser, record)
        typing.assert_type(function, c.Function[list[int], int])
        invocation = c.Invocation("different-name", ["12", "extra"])
        prepared = function.prepare(invocation)
        typing.assert_type(prepared, c.Prepared[list[int]])
        invocation.args[0] = "bad"
        context: list[int] = []
        self.assertEqual(context, [])
        self.assertEqual(parser.calls, [["12", "extra"]])
        await prepared.invoke(context)
        await prepared.invoke(context)
        other: list[int] = []
        await prepared.invoke(other)
        self.assertEqual(context, [12, 12])
        self.assertEqual(other, [12])
        self.assertEqual(len(parser.calls), 1)

    async def test_prepare_errors_match_invoke(self) -> None:
        """Retain the message and original token marks, including missing arguments."""

        async def forbidden(context: None, value: int) -> None:
            """Fail if an invalid invocation executes its handler."""
            raise AssertionError("execution ran")

        function = c.Function(
            "limit", "", p.Remaining(p.Keyword("value", p.Int())), forbidden
        )
        for args in (["value", "bad"], ["value"], ["value", "12", "extra"]):
            with self.subTest(args=args):
                invocation = c.Invocation("LIMIT", args)
                expected = function.parser.parse(args)
                assert isinstance(expected, p.ParseFail)
                with self.assertRaises(c.CommandParseError) as prepared_error:
                    function.prepare(invocation)
                with self.assertRaises(c.CommandParseError) as invoked_error:
                    await function.invoke(None, invocation)
                self.assertEqual(str(prepared_error.exception), expected.message)
                self.assertEqual(str(invoked_error.exception), expected.message)
                self.assertEqual(
                    prepared_error.exception.marked_args,
                    [c.MarkedWord("LIMIT", False)]
                    + c.mark_words(args, expected.processed),
                )
                self.assertEqual(
                    prepared_error.exception.marked_args,
                    invoked_error.exception.marked_args,
                )

    async def test_parser_preserves_results_and_defers_callback(self) -> None:
        """Argument-only parsing preserves partial consumption and failure offsets."""
        calls: list[int] = []

        async def record(context: None, value: int) -> None:
            """Record a validated argument only during invocation."""
            calls.append(value)

        function = c.Function("limit", "", p.Keyword("value", p.Int()), record)
        parser = function.prepared_parser()
        typing.assert_type(parser, p.Parser[c.Prepared[None]])
        result = parser.parse(["value", "12", "extra"])
        assert isinstance(result, p.ParseOK)
        self.assertEqual(result.processed, 2)
        self.assertEqual(calls, [])
        for args in ([], ["value"], ["value", "bad"]):
            self.assertEqual(parser.parse(args), function.parser.parse(args))
        await result.value.invoke(None)
        self.assertEqual(calls, [12])

    async def test_complete_same_name_alternatives_execute_only_selected(self) -> None:
        """Reject partial first matches before selecting a complete same-name branch."""
        calls: list[str] = []

        async def first(context: None, value: int) -> None:
            """Record the short alternative if selected."""
            calls.append("first")

        async def second(context: None, value: tuple[int, bool]) -> None:
            """Record the complete alternative if selected."""
            calls.append(f"second:{value}")

        short = c.Function("set", "", p.Int(), first)
        long = c.Function("set", "", p.Then(p.Int(), p.Bool()), second)
        grammar = p.OneOf(
            p.Keyword("set", p.Remaining(short.prepared_parser())),
            p.Keyword("set", p.Remaining(long.prepared_parser())),
        )
        typing.assert_type(grammar, p.OneOf[c.Prepared[None]])
        result = grammar.parse(["set", "12", "on"])
        assert isinstance(result, p.ParseOK)
        self.assertEqual(result.processed, 3)
        self.assertEqual(calls, [])
        self.assertIsInstance(grammar.parse(["set", "12", "bad"]), p.ParseFail)
        self.assertEqual(calls, [])
        await result.value.invoke(None)
        self.assertEqual(calls, ["second:(12, True)"])

    async def test_callback_exceptions_propagate_without_reparse(self) -> None:
        """Leave application failures intact and keep the prepared handler snapshot."""
        error = RuntimeError("handler failure")
        parser = Counting(p.Int())

        async def fail(context: list[int], value: int) -> None:
            """Record receipt before raising the original application exception."""
            context.append(value)
            raise error

        async def forbidden(context: list[int], value: int) -> None:
            """Detect lookup of the mutable Function callback after preparation."""
            raise AssertionError("replacement callback ran")

        function = c.Function("", "", parser, fail)
        prepared = function.prepare(c.Invocation("", ["12"]))
        function.fn[0] = forbidden
        context: list[int] = []
        with self.assertRaises(RuntimeError) as raised:
            await prepared.invoke(context)
        self.assertIs(raised.exception, error)
        self.assertEqual(context, [12])
        self.assertEqual(len(parser.calls), 1)

    def test_help_does_not_validate_or_execute(self) -> None:
        """Prepared parsing is structurally transparent to help and discovery."""

        def forbidden_validation(value: int) -> int:
            """Detect parsing during help generation."""
            raise AssertionError("validation ran")

        async def forbidden_execution(context: None, value: int) -> None:
            """Detect execution during help generation."""
            raise AssertionError("execution ran")

        function = c.Function(
            "limit", "", p.Map(forbidden_validation, p.Int()), forbidden_execution
        )
        self.assertEqual(
            p.render_help(function.prepared_parser()), p.render_help(function.parser)
        )
        grammar = p.Keyword("limit", function.prepared_parser())
        self.assertEqual(
            p.Help[None]().document(grammar, None).command_names(), {"limit"}
        )


class TestPreparedValue(unittest.IsolatedAsyncioTestCase):
    """Check typed value access without weakening deferred execution contracts."""

    async def test_reference_capture_and_repeated_execution(self) -> None:
        """Expose the exact mutable object and snapshot the callback on success."""
        validations: list[int] = []
        received: list[list[int]] = []

        def validate(value: int) -> list[int]:
            """Build one mutable result and record each validation."""
            validations.append(value)
            return [value]

        async def record(context: list[list[int]], value: list[int]) -> None:
            """Retain the callback argument's identity for inspection."""
            context.append(value)

        async def forbidden(context: list[list[int]], value: list[int]) -> None:
            """Detect callback lookup after successful preparation."""
            raise AssertionError("replacement callback ran")

        parser = Counting(p.Map(validate, p.Int()))
        function = c.Function("", "", parser, record)
        grammar = function.prepared_value_parser()
        typing.assert_type(
            grammar, p.Parser[c.PreparedValue[list[list[int]], list[int]]]
        )
        result = grammar.parse(["12", "tail"])
        assert isinstance(result, p.ParseOK)
        prepared = result.value
        typing.assert_type(prepared.value, list[int])
        self.assertEqual(result.processed, 1)
        self.assertEqual(validations, [12])
        self.assertEqual(received, [])
        with self.assertRaises(dataclasses.FrozenInstanceError):
            setattr(prepared, "value", [99])
        prepared.value.append(13)
        function.fn[0] = forbidden
        await prepared.invoke(received)
        await prepared.invoke(received)
        self.assertEqual(received, [[12, 13], [12, 13]])
        self.assertTrue(all(value is prepared.value for value in received))
        self.assertEqual(parser.calls, [["12", "tail"]])
        self.assertEqual(validations, [12])

    async def test_exceptions_propagate_without_reparsing(self) -> None:
        """Retain exception identity and rerun only the handler on repeated calls."""
        error = RuntimeError("handler failed")
        parser = Counting(p.Int())
        calls: list[int] = []

        async def fail(context: None, value: int) -> None:
            """Record each execution before raising the application exception."""
            calls.append(value)
            raise error

        result = c.Function("", "", parser, fail).prepared_value_parser().parse(["12"])
        assert isinstance(result, p.ParseOK)
        for _ in range(2):
            with self.assertRaises(RuntimeError) as raised:
                await result.value.invoke(None)
            self.assertIs(raised.exception, error)
        self.assertEqual(calls, [12, 12])
        self.assertEqual(parser.calls, [["12"]])

    def test_failures_consumption_and_help_match_opaque_preparation(self) -> None:
        """Keep offsets and grammar transparent without running validators for help."""
        validations: list[int] = []

        def validate(value: int) -> int:
            """Record validation so help traversal can be checked for side effects."""
            validations.append(value)
            return value

        async def forbidden(context: None, value: int) -> None:
            """Detect handler execution during validation or help traversal."""
            raise AssertionError("handler ran")

        function = c.Function(
            "", "", p.Keyword("value", p.Map(validate, p.Int())), forbidden
        )
        typed = function.prepared_value_parser()
        opaque = function.prepared_parser()
        self.assertEqual(p.render_help(typed), p.render_help(opaque))
        document = p.Help[None]().document(p.Keyword("limit", typed), None)
        self.assertEqual(document.command_names(), {"limit"})
        self.assertEqual(validations, [])
        for args in ([], ["value"], ["value", "bad"]):
            self.assertEqual(typed.parse(args), opaque.parse(args))
        for args in (["value", "12"], ["value", "12", "tail"]):
            result = typed.parse(args)
            other = opaque.parse(args)
            assert isinstance(result, p.ParseOK)
            assert isinstance(other, p.ParseOK)
            self.assertEqual(result.processed, other.processed)
            self.assertEqual(result.value.value, 12)
        self.assertEqual(
            p.Remaining(typed).parse(["value", "12", "tail"]),
            p.Remaining(opaque).parse(["value", "12", "tail"]),
        )

    async def test_branch_local_completeness_with_typed_results(self) -> None:
        """Select only a complete branch while preserving a shared value type."""
        calls: list[str] = []

        async def record(context: str, value: int) -> None:
            """Identify the selected branch through its parsed integer."""
            calls.append(f"{context}:{value}")

        short = c.Function("set", "", p.Int(), record)
        long = c.Function("set", "", p.Keyword("12", p.Int()), record)
        grammar = p.OneOf(
            p.Keyword("set", p.Remaining(short.prepared_value_parser())),
            p.Keyword("set", p.Remaining(long.prepared_value_parser())),
        )
        typing.assert_type(grammar, p.OneOf[c.PreparedValue[str, int]])
        result = grammar.parse(["set", "12", "34"])
        assert isinstance(result, p.ParseOK)
        self.assertEqual(result.processed, 3)
        self.assertEqual(result.value.value, 34)
        self.assertEqual(calls, [])
        self.assertIsInstance(grammar.parse(["set", "12", "bad"]), p.ParseFail)
        self.assertEqual(calls, [])
        await result.value.invoke("selected")
        self.assertEqual(calls, ["selected:34"])
