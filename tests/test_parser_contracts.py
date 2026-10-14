"""Pin complete-token parsing, input ownership, and combinator edge cases."""

import unittest

import argparsec.parser as p


class TestParserContracts(unittest.TestCase):
    """Protect reusable parser behavior without application dependencies."""

    def test_int_consumes_one_complete_numeric_token(self) -> None:
        """Accept unsigned integers without consuming the following token."""
        for token, value in [("0", 0), ("123", 123), ("00123", 123)]:
            with self.subTest(token=token):
                self.assertEqual(p.Int().parse([token, "tail"]), p.ParseOK(value, 1))

    def test_int_rejects_partial_or_invalid_tokens(self) -> None:
        """Reject suffixes, decimals, whitespace, and signs without consumption."""
        self.assertEqual(p.Int().parse([]), p.ParseFail("No argument provided", 0))
        for token in ["", "123abc", "123.5", "123\n", "123 ", "-123", "+123"]:
            with self.subTest(token=token):
                result = p.Int().parse([token])
                self.assertIsInstance(result, p.ParseFail)
                assert isinstance(result, p.ParseFail)
                self.assertEqual(result.processed, 0)

    def test_float_consumes_one_complete_numeric_token(self) -> None:
        """Accept unsigned integer and decimal forms, leaving later tokens alone."""
        for token, value in [("0", 0.0), ("123", 123.0), ("12.34", 12.34)]:
            with self.subTest(token=token):
                self.assertEqual(p.Float().parse([token, "tail"]), p.ParseOK(value, 1))

    def test_float_rejects_partial_or_invalid_tokens(self) -> None:
        """Malformed decimals fail normally instead of swallowing text or raising."""
        self.assertEqual(p.Float().parse([]), p.ParseFail("No argument provided", 0))
        for token in [
            "",
            "123abc",
            "12x34",
            "12,34",
            "12.34abc",
            "12.34.56",
            "12\n34",
            "12.34\n",
            "12 ",
            "12.",
            ".5",
            "-12.5",
            "+12.5",
            "1e3",
        ]:
            with self.subTest(token=token):
                result = p.Float().parse([token])
                self.assertIsInstance(result, p.ParseFail)
                assert isinstance(result, p.ParseFail)
                self.assertEqual(result.processed, 0)

    def test_float_suffix_requires_a_literal_decimal_point(self) -> None:
        """Require well-formed numeric tokens in joined and separate unit forms."""
        parser = p.PosFloatSuffix(["m", "km"])
        for args in [["12.5km"], ["12.5", "km"]]:
            with self.subTest(args=args):
                self.assertEqual(
                    parser.parse(args), p.ParseOK(p.SuffixInfo(12.5, "km"), len(args))
                )
        for args in [
            ["12x5km"],
            ["12,5km"],
            ["12.5kmabc"],
            ["12.5km\n"],
            ["12x5", "km"],
        ]:
            with self.subTest(args=args):
                self.assertIsInstance(parser.parse(args), p.ParseFail)

    def test_url_normalizes_without_modifying_input(self) -> None:
        """Normalize Slack links in the result, never in caller-owned tokens."""
        for token, expected in [
            ("https://example.com/?a=1&b=2", "https://example.com/?a=1&b=2"),
            ("<https://example.com/?a=1&amp;b=2>", "https://example.com/?a=1&b=2"),
        ]:
            with self.subTest(token=token):
                args = [token, "tail"]
                for _ in range(2):
                    self.assertEqual(p.Url().parse(args), p.ParseOK(expected, 1))
                    self.assertEqual(args, [token, "tail"])
        self.assertEqual(p.Url().parse([]), p.ParseFail("No argument provided", 0))

    def test_url_does_not_change_input_seen_by_an_alternative(self) -> None:
        """A failed URL branch must leave the original spelling for later branches."""
        token = "<https://example.com/?a=1&amp;b=2>"
        parser = p.OneOf(
            p.Remaining(p.Url()),
            p.CaptureFixedStr(token),
        )
        args = [token, "tail"]
        self.assertEqual(parser.parse(args), p.ParseOK(token, 1))
        self.assertEqual(args, [token, "tail"])

    def test_one_of_accepts_empty_input_when_an_alternative_does(self) -> None:
        """A choice delegates empty-input acceptance to its alternatives."""
        self.assertEqual(p.OneOf(p.Empty()).parse([]), p.ParseOK((), 0))
        self.assertEqual(p.OneOf(p.Optional_(p.Int())).parse([]), p.ParseOK(None, 0))
        self.assertEqual(p.OneOf(p.List_(p.Int())).parse([]), p.ParseOK([], 0))

    def test_one_of_tries_later_alternatives_on_empty_input(self) -> None:
        """A failed required parser must not hide a later optional alternative."""
        self.assertEqual(
            p.OneOf(p.Int().any(), p.Empty().any()).parse([]), p.ParseOK((), 0)
        )

    def test_one_of_preserves_first_success_even_without_consumption(self) -> None:
        """An optional first alternative wins on both empty and invalid input."""
        parser = p.OneOf(p.Optional_(p.Int()).any(), p.AnyStr().any())
        for args in [[], ["invalid"]]:
            with self.subTest(args=args):
                self.assertEqual(parser.parse(args), p.ParseOK(None, 0))
        self.assertEqual(parser.parse(["123"]), p.ParseOK(123, 1))

    def test_one_of_rejects_empty_input_when_all_alternatives_do(self) -> None:
        """Required alternatives retain ordinary choice failure diagnostics."""
        self.assertEqual(p.OneOf(p.Int()).parse([]), p.ParseFail("Invalid value", 0))
        self.assertEqual(
            p.OneOf(p.Labeled("integer", p.Int())).parse([]),
            p.ParseFail("Invalid value (expected one of integer)", 0),
        )

    def test_optional_preserves_empty_success_and_discards_failures(self) -> None:
        """Try empty input and turn even partially consumed failures into absence."""
        self.assertEqual(p.Optional_(p.Empty()).parse([]), p.ParseOK((), 0))
        self.assertEqual(p.Optional_(p.Int()).parse([]), p.ParseOK(None, 0))
        self.assertEqual(
            p.Optional_(p.Keyword("value", p.Int())).parse(["value", "invalid"]),
            p.ParseOK(None, 0),
        )

    def test_list_accepts_empty_input_and_stops_before_failure(self) -> None:
        """Return parsed prefixes, discarding consumption reported by a failed item."""
        self.assertEqual(p.List_(p.Empty()).parse([]), p.ParseOK([], 0))
        parser = p.List_(p.Keyword("value", p.Int()))
        self.assertEqual(parser.parse(["value", "invalid"]), p.ParseOK([], 0))
        self.assertEqual(
            parser.parse(["value", "1", "value", "invalid"]), p.ParseOK([1], 2)
        )

    def test_list_rejects_zero_consumption_success_on_nonempty_input(self) -> None:
        """A successful empty item must fail rather than permit an infinite loop."""
        result = p.List_(p.Optional_(p.Int())).parse(["invalid"])
        self.assertIsInstance(result, p.ParseFail)
        assert isinstance(result, p.ParseFail)
        self.assertEqual(result.processed, 0)
