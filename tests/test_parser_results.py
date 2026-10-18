"""Protect result behavior and exhaustive narrowing of the public union."""

import typing
import unittest

import argparsec as p


def describe_result(result: p.ParseResult[int]) -> tuple[str, int]:
    """Match both variants, requiring mypy to preserve types and exhaustiveness."""
    match result:
        case p.ParseOK(value=value, processed=processed):
            typing.assert_type(value, int)
            return str(value), processed
        case p.ParseFail(message=message, processed=processed):
            typing.assert_type(message, str)
            return message, processed
        case _:
            typing.assert_never(result)


class TestParserResults(unittest.TestCase):
    """Check matching, equality, and formatting of the union's concrete variants."""

    def test_match_extracts_both_result_variants(self) -> None:
        """Exercise the same exhaustive match with success and failure results."""
        parser = p.Remaining(p.Keyword("limit", p.Int()))
        self.assertEqual(describe_result(parser.parse(["limit", "80"])), ("80", 2))
        failure = parser.parse(["limit", "invalid"])
        assert isinstance(failure, p.ParseFail)
        self.assertEqual(describe_result(failure), (failure.message, failure.processed))

    def test_result_equality_compares_variant_and_fields(self) -> None:
        """Compare values, consumption, and variant identity structurally."""
        self.assertEqual(p.ParseOK(80, 2), p.ParseOK(80, 2))
        self.assertEqual(p.ParseFail("invalid", 1), p.ParseFail("invalid", 1))
        self.assertNotEqual(p.ParseOK(80, 2), p.ParseOK(81, 2))
        self.assertNotEqual(p.ParseOK(80, 2), p.ParseOK(80, 1))
        self.assertNotEqual(p.ParseFail("invalid", 1), p.ParseFail("other", 1))
        self.assertNotEqual(p.ParseFail("invalid", 1), p.ParseFail("invalid", 2))
        self.assertNotEqual(p.ParseOK("invalid", 1), p.ParseFail("invalid", 1))
        self.assertNotEqual(p.ParseFail("invalid", 1), p.ParseOK("invalid", 1))
        self.assertNotEqual(p.ParseOK(80, 2), object())
        self.assertNotEqual(p.ParseFail("invalid", 1), object())

    def test_result_string_formatting_matches_representation(self) -> None:
        """Render both str and repr with the variant name and its fields."""
        for result, expected in [
            (p.ParseOK(80, 2), "ParseOK(80, 2)"),
            (p.ParseOK("value", 1), 'ParseOK("value", 1)'),
            (p.ParseFail("invalid", 1), 'ParseFail("invalid", 1)'),
        ]:
            with self.subTest(expected=expected):
                self.assertEqual(str(result), expected)
                self.assertEqual(repr(result), expected)
