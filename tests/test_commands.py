"""Verify independent command tokenization, diagnostics, and async dispatch."""

import unittest

import argparsec as p
import argparsec.commands as c


class TestCommands(unittest.IsolatedAsyncioTestCase):
    """Exercise command dispatch without application or transport dependencies."""

    def setup_commands[Result](
        self, called: list[Result | None], valid: p.Parser[Result]
    ) -> c.Commands[None]:
        """Bind two independent recording callbacks to a shared argument parser."""
        commands = c.Commands[None]()

        async def command0(context: None, value: Result) -> None:
            """Record only the first handler's parsed value."""
            called[0] = value

        async def command1(context: None, value: Result) -> None:
            """Record only the second handler's parsed value."""
            called[1] = value

        commands.register(c.Function("test0", "first", valid, command0))
        commands.register(c.Function("test1", "second", valid, command1))
        return commands

    async def test_simple_call(self) -> None:
        """Dispatch an argument-free command without running the other handler."""
        called: list[p.EmptyVal | None] = [None, None]
        commands = self.setup_commands(called, p.Empty())
        await commands.invoke(None, c.Invocation("test0", []))
        self.assertEqual(called, [(), None])

    async def test_validated_call(self) -> None:
        """Pass a parsed value only to the named handler."""
        called: list[str | None] = [None, None]
        commands = self.setup_commands(called, p.AnyStr())
        await commands.invoke(None, c.Invocation("test0", ["arg1"]))
        self.assertEqual(called, ["arg1", None])

    async def test_case_insensitive_dispatch_and_help(self) -> None:
        """Match names case-insensitively while retaining registered help spelling."""
        called: list[int | None] = [None, None]
        commands = self.setup_commands(called, p.Int())
        self.assertTrue(commands.has_command("TEST1"))
        await commands.invoke(None, c.Invocation("TEST1", ["80"]))
        self.assertEqual(called, [None, 80])
        self.assertEqual(commands.help(), "test0: first\ntest1: second")

    async def test_invalid_arguments_preserve_diagnostics_without_execution(
        self,
    ) -> None:
        """Retain parser messages and original token highlighting on rejection."""
        called: list[int | None] = [None, None]
        grammar = p.Remaining(p.Keyword("value", p.Int()))
        commands = self.setup_commands(called, grammar)
        invocation = c.Invocation("test0", ["value", "invalid"])
        failure = grammar.parse(invocation.args)
        assert isinstance(failure, p.ParseFail)
        with self.assertRaises(c.CommandParseError) as raised:
            await commands.invoke(None, invocation)
        self.assertEqual(str(raised.exception), failure.message)
        self.assertEqual(
            raised.exception.marked_args,
            [
                c.MarkedWord("test0", False),
                c.MarkedWord("value", False),
                c.MarkedWord("invalid", True),
            ],
        )
        self.assertEqual(called, [None, None])

    async def test_parser_defers_execution_and_argument_validation(self) -> None:
        """Known names produce callbacks, even when arguments will later fail."""
        called: list[int | None] = [None, None]
        commands = self.setup_commands(called, p.Remaining(p.Int()))
        result = commands.parser().parse(["TEST0", "80"])
        assert isinstance(result, p.ParseOK)
        self.assertEqual(result.processed, 2)
        self.assertEqual(called, [None, None])
        await result.value(None)
        self.assertEqual(called, [80, None])
        invalid = commands.parser().parse(["test1", "invalid"])
        assert isinstance(invalid, p.ParseOK)
        with self.assertRaises(c.CommandParseError):
            await invalid.value(None)
        self.assertEqual(called, [80, None])

    async def test_parser_rejects_missing_and_unknown_names(self) -> None:
        """Return ordinary parse failures before constructing unknown invocations."""
        parser = c.Commands[None]().parser()
        self.assertEqual(parser.parse([]), p.ParseFail("No command name", 0))
        self.assertEqual(
            parser.parse(["missing"]), p.ParseFail("No such command: missing", 0)
        )

    async def test_context_and_callback_errors_are_preserved(self) -> None:
        """Pass the original context and propagate callback exceptions unchanged."""
        commands = c.Commands[list[int]]()
        error = RuntimeError("callback diagnostic")

        async def record_then_fail(context: list[int], value: int) -> None:
            """Record receipt of context and value before raising the original error."""
            context.append(value)
            raise error

        commands.register(c.Function("limit", "set a limit", p.Int(), record_then_fail))
        context: list[int] = []
        with self.assertRaises(RuntimeError) as raised:
            await commands.invoke(context, c.Invocation("limit", ["80"]))
        self.assertIs(raised.exception, error)
        self.assertEqual(context, [80])

    async def test_duplicate_matches_execute_in_registration_order(self) -> None:
        """Preserve sequential duplicate-name handling rather than silently replacing it."""
        commands = c.Commands[list[str]]()

        async def first(context: list[str], value: str) -> None:
            """Record execution of the first matching handler."""
            context.append("first:" + value)

        async def second(context: list[str], value: str) -> None:
            """Record execution of the second matching handler."""
            context.append("second:" + value)

        commands.register(c.Function("record", "", p.AnyStr(), first))
        commands.register(c.Function("RECORD", "", p.AnyStr(), second))
        context: list[str] = []
        await commands.invoke(context, c.Invocation("record", ["value"]))
        self.assertEqual(context, ["first:value", "second:value"])
        await commands.invoke(context, c.Invocation("missing", []))
        self.assertEqual(context, ["first:value", "second:value"])

    async def test_registry_parser_observes_later_registration(self) -> None:
        """An already-created parser must use the current registry contents."""
        commands = c.Commands[list[int]]()
        parser = commands.parser()
        self.assertIsInstance(parser.parse(["limit", "80"]), p.ParseFail)

        async def record(context: list[int], value: int) -> None:
            """Store a parsed integer in the supplied context."""
            context.append(value)

        commands.register(c.Function("limit", "", p.Int(), record))
        result = parser.parse(["limit", "80"])
        assert isinstance(result, p.ParseOK)
        context: list[int] = []
        await result.value(context)
        self.assertEqual(context, [80])


class TestInvocation(unittest.TestCase):
    """Exercise the optional literal-space tokenizer and diagnostic data model."""

    def test_spaces_comments_and_argument_spelling(self) -> None:
        """Strip hash comments and empty space-delimited fields, preserving token case."""
        self.assertEqual(
            c.Invocation.parse("  LIMIT   80 Roadster # ignored"),
            c.Invocation("LIMIT", ["80", "Roadster"]),
        )

    def test_empty_and_comment_only_inputs(self) -> None:
        """All tokenless invocations raise the dedicated parse exception."""
        for text in ["", "   ", "# comment", "  # comment"]:
            with self.subTest(text=text):
                with self.assertRaises(c.InvocationEmptyError):
                    c.Invocation.parse(text)

    def test_log_retains_command_and_arguments(self) -> None:
        """Keep the original useful DEBUG payload with normal logger propagation."""
        with self.assertLogs("argparsec.commands", level="DEBUG") as captured:
            c.Invocation.parse("share https://example.com/payload Roadster")
        output = "\n".join(captured.output)
        self.assertIn("share", output)
        self.assertIn("https://example.com/payload", output)
        self.assertIn("Roadster", output)

    def test_mark_words_uses_token_offsets(self) -> None:
        """Mark the offending argument, leaving end-of-input failures unmarked."""
        self.assertEqual(
            c.mark_words(["a", "b"], 1),
            [c.MarkedWord("a", False), c.MarkedWord("b", True)],
        )
        self.assertEqual(c.mark_words(["a"], 1), [c.MarkedWord("a", False)])

    def test_empty_registry_help(self) -> None:
        """An empty command registry has no help lines or matching names."""
        commands = c.Commands[None]()
        self.assertEqual(commands.help(), "")
        self.assertFalse(commands.has_command("missing"))
