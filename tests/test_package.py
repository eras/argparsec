"""Verify the installed package's public API and independent utilities."""

import datetime
import unittest

import argparsec as p
import argparsec.parser as parser
import argparsec.utils as utils


class TestPackage(unittest.TestCase):
    """Exercise the supported import path and the extracted helper contracts."""

    def test_public_exports_share_parser_types(self) -> None:
        """Root exports must be the same objects used by the parser module."""
        for name in p.__all__:
            with self.subTest(name=name):
                self.assertIs(getattr(p, name), getattr(parser, name))

    def test_readme_example(self) -> None:
        """Keep the documented complete-command example executable."""
        grammar = p.Remaining(p.Keyword("limit", p.Int()))
        result = grammar.parse(["limit", "80"])
        self.assertIsInstance(result, p.ParseOK)
        assert isinstance(result, p.ParseOK)
        self.assertEqual(result.value, 80)
        self.assertEqual(result.processed, 2)
        self.assertIsInstance(grammar.parse(["limit", "80", "extra"]), p.ParseFail)

    def test_coalesce_preserves_false_values(self) -> None:
        """Only None is absent, and an entirely absent sequence is an error."""
        self.assertEqual(utils.coalesce(None, 0, 1), 0)
        self.assertFalse(utils.coalesce(None, False, True))
        with self.assertRaises(AssertionError):
            utils.coalesce(None)

    def test_map_optional_skips_absent_values(self) -> None:
        """Absent input must not invoke a potentially effectful conversion."""
        calls: list[int] = []
        self.assertIsNone(utils.map_optional(None, calls.append))
        self.assertEqual(calls, [])
        self.assertEqual(utils.map_optional("12", int), 12)

    def test_assert_some_preserves_values_and_reports_absence(self) -> None:
        """Keep assertion behavior and caller-supplied diagnostic messages."""
        self.assertEqual(utils.assert_some(0), 0)
        with self.assertRaisesRegex(AssertionError, "missing value"):
            utils.assert_some(None, "missing value")

    def test_round_to_next_second_advances_even_exact_seconds(self) -> None:
        """Preserve strict advancement and rollover, including timezone information."""
        start = datetime.datetime(2026, 1, 1, 23, 59, 59, tzinfo=datetime.timezone.utc)
        expected = datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc)
        self.assertEqual(utils.round_to_next_second(start), expected)
        self.assertEqual(
            utils.round_to_next_second(start.replace(microsecond=123)), expected
        )
