"""Generic sequence parser tests, independent of TeslaBot."""

import unittest
from unittest import mock
import argparsec.parser as p


class TestSeparated(unittest.TestCase):
    """Exercise full validation, ambiguity, diagnostics, and speculative parsing."""

    def test_complete_items_and_case_insensitive_separator(self) -> None:
        """Accept ordered items even when the item parser requires end of input."""
        parser = p.Separated(p.Adjacent(p.Bool(), p.Empty()), "and")
        for args, values in [
            (["on"], [(True, ())]),
            (["on", "AnD", "off", "and", "on"], [(True, ()), (False, ()), (True, ())]),
        ]:
            with self.subTest(args=args):
                self.assertEqual(parser.parse(args), p.ParseOK(values, len(args)))

    def test_whole_item_wins(self) -> None:
        """Retain literal separators when an unsplit command is actually valid."""
        parser = p.Separated(p.RestAsStr(), "and")
        self.assertEqual(
            parser.parse(["hello", "and", "goodbye"]),
            p.ParseOK(["hello and goodbye"], 3),
        )

    def test_longest_valid_prefix_and_backtracking(self) -> None:
        """Prefer longer items but revisit them when their remaining sequence fails."""
        parser = p.Separated(
            p.OneOf(
                p.Map(
                    lambda _: "long",
                    p.Remaining(
                        p.Seq(
                            [
                                p.CaptureFixedStr("a"),
                                p.CaptureFixedStr("and"),
                                p.CaptureFixedStr("b"),
                            ]
                        )
                    ),
                ),
                p.Map(lambda _: "a", p.Remaining(p.CaptureFixedStr("a"))),
                p.Map(
                    lambda _: "tail",
                    p.Remaining(
                        p.Seq(
                            [
                                p.CaptureFixedStr("b"),
                                p.CaptureFixedStr("and"),
                                p.CaptureFixedStr("c"),
                            ]
                        )
                    ),
                ),
            ),
            "and",
        )
        self.assertEqual(
            parser.parse("a and b and c".split()), p.ParseOK(["a", "tail"], 5)
        )
        longest = p.Separated(
            p.OneOf(
                parser.parser, p.Map(lambda _: "c", p.Remaining(p.CaptureFixedStr("c")))
            ),
            "and",
        )
        self.assertEqual(
            longest.parse("a and b and c".split()),
            p.ParseOK(["long", "c"], 5),
        )

    def test_reject_empty_and_invalid_items(self) -> None:
        """Never accept empty input, empty segments, or a merely valid prefix."""
        parser = p.Separated(p.Bool(), "and")
        for args, offset in [
            ([], 0),
            (["and", "on"], 0),
            (["on", "and"], 2),
            (["on", "and", "and", "off"], 2),
            (["on", "off"], 1),
            (["on", "and", "off", "junk"], 3),
            (["on", "and", "off", "and", "invalid"], 4),
        ]:
            with self.subTest(args=args):
                result = parser.parse(args)
                assert isinstance(result, p.ParseFail)
                self.assertEqual(result.processed, offset)
        self.assertIsInstance(p.Separated(p.Empty(), "and").parse([]), p.ParseFail)
        self.assertIsInstance(
            p.Separated(p.Optional_(p.Bool()), "and").parse(["and"]), p.ParseFail
        )

    def test_preserve_failure_details(self) -> None:
        """Forward a later command's exact message and add its original token offset."""
        item = p.Keyword("climate", p.Remaining(p.Bool()))
        parser = p.Separated(item, "and")
        args = "climate on and climate off and climate invalid".split()
        failure = item.parse(["climate", "invalid"])
        assert isinstance(failure, p.ParseFail)
        self.assertEqual(parser.parse(args), failure.forward(processed=6))
        self.assertEqual(parser.parse(["climate", "invalid"]), failure)

    def test_does_not_mutate_input(self) -> None:
        """Isolate parsers such as Url that normalize their supplied token list."""
        args = ["<https://example.com?a=1&amp;b=2>", "and", "<https://example.com>"]
        original = args[:]
        self.assertEqual(
            p.Separated(p.Url(), "and").parse(args),
            p.ParseOK(["https://example.com?a=1&b=2", "https://example.com"], 3),
        )
        self.assertEqual(args, original)

    def test_callbacks_are_not_executed(self) -> None:
        """Complete validation constructs callbacks but executes none, even on failure."""
        calls: list[bool] = []

        def record(args: bool) -> None:
            """Record execution separately from speculative callback construction."""
            calls.append(args)

        parser = p.Separated(p.Callback(record, p.Bool()), "and")
        result = parser.parse(["on", "and", "off"])
        assert isinstance(result, p.ParseOK)
        self.assertEqual(calls, [])
        self.assertIsInstance(parser.parse(["on", "and", "invalid"]), p.ParseFail)
        self.assertEqual(calls, [])
        for callback in result.value:
            callback()
        self.assertEqual(calls, [True, False])

    def test_long_sequence(self) -> None:
        """Validate many short items without depending on Python's recursion limit."""
        args = ["on", "and"] * 1100 + ["off"]
        self.assertEqual(
            p.Separated(p.Bool(), "and").parse(args),
            p.ParseOK([True] * 1100 + [False], len(args)),
        )

    def test_adjacent_does_not_retry_identical_prefixes(self) -> None:
        """Keep failed left searches linear in prefix count for each priority pass."""
        left = mock.Mock(wraps=p.CaptureFixedStr("missing"))
        args = ["noise"] * 20
        self.assertEqual(
            p.Adjacent(left, p.Empty()).parse(args),
            p.ParseFail("No adjacent arguments parsed completely", 0),
        )
        self.assertEqual(left.parse.call_count, 2 * (len(args) + 1))

    def test_cache_restored_after_nested_parse_and_exception(self) -> None:
        """Nested invocations restore the parent's cache, and exceptions discard it."""

        def nested_then_raise(value: str) -> str:
            """Exercise cache nesting before propagating a speculative parser error."""
            parent = p.Adjacent._parse_cache.get()
            self.assertIsNotNone(parent)
            inner = p.Separated(p.Adjacent(p.AnyStr(), p.Empty()), "and")
            self.assertEqual(inner.parse([value]), p.ParseOK([(value, ())], 1))
            self.assertIs(p.Adjacent._parse_cache.get(), parent)
            raise ValueError("speculative parser error")

        parser = p.Separated(
            p.Adjacent(p.Map(nested_then_raise, p.AnyStr()), p.Empty()), "and"
        )
        self.assertIsNone(p.Adjacent._parse_cache.get())
        with self.assertRaisesRegex(ValueError, "speculative parser error"):
            parser.parse(["outer"])
        self.assertIsNone(p.Adjacent._parse_cache.get())

    def test_cached_adjacent_isolates_mutating_children(self) -> None:
        """Cache normalized results without letting Url mutate the caller's input."""
        url = "<https://example.com?a=1&amp;b=2>"
        args = [url, "and", url]
        parser = p.Separated(p.Adjacent(p.Url(), p.Empty()), "and")
        self.assertEqual(
            parser.parse(args),
            p.ParseOK([("https://example.com?a=1&b=2", ())] * 2, 3),
        )
        self.assertEqual(args, [url, "and", url])
