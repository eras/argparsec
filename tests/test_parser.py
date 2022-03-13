import asyncio

import unittest

from typing import List, TypeVar, Optional, Tuple

import argparsec.parser as p

Result = TypeVar('Result', bound=object)

class TestParser(unittest.TestCase):
    def __init__(self, method_name: str) -> None:
        super().__init__(method_name)
        self.longMessage = True

    def test_simple_validators(self) -> None:
        with self.subTest():
            self.assertEqual(p.VldEmpty().validate([]),
                             p.ValidatorOK((), processed=0))
        with self.subTest():
            self.assertEqual(p.VldEmpty().validate(["hei"]),
                             p.ValidatorFail("Expected no more arguments"))
        with self.subTest():
            self.assertEqual(p.VldAnyStr().validate([]),
                             p.ValidatorFail("No argument provided"))
        with self.subTest():
            self.assertEqual(p.VldAnyStr().validate([""]),
                             p.ValidatorOK("", processed=1))
        with self.subTest():
            self.assertEqual(p.VldAnyStr().validate(["moi"]),
                             p.ValidatorOK("moi", processed=1))
        with self.subTest():
            self.assertEqual(p.VldAnyStr().validate(["moi", "moi"]),
                             p.ValidatorOK("moi", processed=1))

    def test_bool(self) -> None:
        with self.subTest():
            self.assertEqual(p.VldBool().validate([]),
                             p.ValidatorFail("No argument provided"))
        with self.subTest():
            self.assertEqual(p.VldBool().validate([""]),
                             p.ValidatorFail('Invalid argument "" for boolean'))
        with self.subTest():
            self.assertEqual(p.VldBool().validate(["moi"]),
                             p.ValidatorFail('Invalid argument "moi" for boolean'))
        with self.subTest():
            self.assertEqual(p.VldBool().validate(["True"]),
                             p.ValidatorOK(True, processed=1))
        with self.subTest():
            self.assertEqual(p.VldBool().validate(["true"]),
                             p.ValidatorOK(True, processed=1))
        with self.subTest():
            self.assertEqual(p.VldBool().validate(["FALSE"]),
                             p.ValidatorOK(False, processed=1))
        with self.subTest():
            self.assertEqual(p.VldBool().validate(["false"]),
                             p.ValidatorOK(False, processed=1))
        with self.subTest():
            self.assertEqual(p.VldBool().validate(["0"]),
                             p.ValidatorOK(False, processed=1))
        with self.subTest():
            self.assertEqual(p.VldBool().validate(["1"]),
                             p.ValidatorOK(True, processed=1))
        with self.subTest():
            self.assertEqual(p.VldBool().validate(["off"]),
                             p.ValidatorOK(False, processed=1))
        with self.subTest(): self.assertEqual(p.VldBool().validate(["on"]),
                                              p.ValidatorOK(True, processed=1))

    def test_regex(self) -> None:
        with self.subTest():
            self.assertEqual(p.VldRegex(r".*", [0]).validate([""]),
                             p.ValidatorOK("", processed=1))
        with self.subTest():
            self.assertEqual(p.VldRegex(r".*", [0]).validate(["moi"]),
                             p.ValidatorOK("moi", processed=1))
        with self.subTest():
            self.assertEqual(p.VldRegex(r".(oi)", [0]).validate(["moi"]),
                             p.ValidatorOK("moi", processed=1))
        with self.subTest():
            self.assertEqual(p.VldRegex(r".(oi)", [1]).validate(["moi"]),
                             p.ValidatorOK("oi", processed=1))
        with self.subTest():
            self.assertEqual(p.VldRegex(r".(o)(i)", [1, 2]).validate(["moi"]),
                             p.ValidatorOK(("o", "i"), processed=1))

    def test_map(self) -> None:
        def negate(x: bool) -> bool:
            return not x
        with self.subTest():
            self.assertEqual(p.VldMap(p.VldBool(), negate).validate([]),
                             p.ValidatorFail("No argument provided"))
        with self.subTest():
            self.assertEqual(p.VldMap(p.VldBool(), negate).validate(["true"]),
                             p.ValidatorOK(False, processed=1))
        with self.subTest():
            self.assertEqual(p.VldMap(p.VldBool(), negate).validate(["false"]),
                             p.ValidatorOK(True, processed=1))

    def test_optional(self) -> None:
        with self.subTest():
            self.assertEqual(p.VldOptional(p.VldBool()).validate([]),
                             p.ValidatorOK(None, processed=0))
        with self.subTest():
            self.assertEqual(p.VldOptional(p.VldBool()).validate(["moi"]),
                             p.ValidatorOK(None, processed=0))
        with self.subTest():
            self.assertEqual(p.VldOptional(p.VldBool()).validate(["true"]),
                             p.ValidatorOK(True, processed=1))

        with self.subTest():
            self.assertEqual(p.VldValidOrMissing(p.VldBool()).validate([]),
                             p.ValidatorOK(None, processed=0))
        with self.subTest():
            self.assertEqual(p.VldValidOrMissing(p.VldBool()).validate(["moi"]),
                             p.ValidatorFail('Invalid argument "moi" for boolean'))
        with self.subTest():
            self.assertEqual(p.VldValidOrMissing(p.VldBool()).validate(["true"]),
                             p.ValidatorOK(True, processed=1))

    def test_adjacent(self) -> None:
        with self.subTest():
            self.assertEqual(p.VldAdjacent(p.VldBool(),
                                           p.VldBool()).validate([]),
                             p.ValidatorFail("No argument provided while parsing first argument"))
        with self.subTest():
            self.assertEqual(p.VldAdjacent(p.VldBool(),
                                           p.VldBool()).validate(["moi"]),
                             p.ValidatorFail('Invalid argument "moi" for boolean while parsing first argument'))
        with self.subTest():
            self.assertEqual(p.VldAdjacent(p.VldBool(),
                                           p.VldBool()).validate(["moi", "1"]),
                             p.ValidatorFail('Invalid argument "moi" for boolean while parsing first argument'))
        with self.subTest():
            self.assertEqual(p.VldAdjacent(p.VldBool(),
                                           p.VldBool()).validate(["1"]),
                             p.ValidatorFail("No argument provided while parsing second argument"))
        with self.subTest():
            self.assertEqual(p.VldAdjacent(p.VldBool(),
                                           p.VldBool()).validate(["1", "moi"]),
                             p.ValidatorFail('Invalid argument "moi" for boolean while parsing second argument'))
        with self.subTest():
            self.assertEqual(p.VldAdjacent(p.VldBool(),
                                           p.VldBool()).validate(["1", "0"]),
                             p.ValidatorOK((True, False), processed=2))
        with self.subTest():
            self.assertEqual(p.VldAdjacent(p.VldBool(),
                                           p.VldAdjacent(p.VldBool(),
                                                         p.VldEmpty())).validate(["1", "0"]),
                             p.ValidatorOK((True, (False, ())), processed=2))

    def test_seq(self) -> None:
        with self.subTest():
            self.assertEqual(p.VldSeq([p.VldBool(),
                                       p.VldBool()]).validate([]),
                             p.ValidatorFail("No argument provided while parsing argument 1"))

        with self.subTest():
            self.assertEqual(p.VldSeq([p.VldBool(),
                                       p.VldBool()]).validate(["moi"]),
                             p.ValidatorFail('Invalid argument "moi" for boolean while parsing argument 1'))

        with self.subTest():
            self.assertEqual(p.VldSeq([p.VldBool(),
                                       p.VldBool()]).validate(["moi", "moi"]),
                             p.ValidatorFail('Invalid argument "moi" for boolean while parsing argument 1'))

        with self.subTest():
            self.assertEqual(p.VldSeq([p.VldBool(),
                                       p.VldBool()]).validate(["1", "moi"]),
                             p.ValidatorFail('Invalid argument "moi" for boolean while parsing argument 2'))

        with self.subTest():
            self.assertEqual(p.VldSeq([p.VldBool(),
                                       p.VldBool()]).validate(["1", "0"]),
                             p.ValidatorOK([True, False], processed=2))
        with self.subTest():
            self.assertEqual(c
                             .VldSeq([p.VldSeq([p.VldMap(p.VldBool(), str).base(),
                                                p.VldMap(p.VldAnyStr(), str)]),
                                      p.VldMap[bool, List[str]](p.VldBool(), lambda x: [str(x)]),
                                      p.VldMap[p.Empty, List[str]](p.VldEmpty(), lambda _: [])])
                             .validate(["1", "moi", "0"]),
                             p.ValidatorOK([["True", "moi"], ["False"], []], processed=3))

        # this is probably more practical though less safely typed..
        with self.subTest():
            self.assertEqual(c
                             .VldSeq([p.VldSeq([p.VldBool().any(),
                                                p.VldAnyStr().any()]),
                                      p.VldBool().any(),
                                      p.VldEmpty().any()])
                             .validate(["1", "moi", "0"]),
                             p.ValidatorOK([[True, "moi"], False, ()], processed=3))

        with self.subTest():
            self.assertEqual(p.VldTag("tag", p.VldBool())
                             .validate([]),
                             p.ValidatorFail("No argument provided"))
        with self.subTest():
            self.assertEqual(p.VldTag("tag", p.VldBool())
                             .validate(["true"]),
                             p.ValidatorOK(("tag", True), processed=1))
        with self.subTest():
            self.assertEqual(p.VldSeq([p.VldTag("tag1", p.VldBool()),
                                       p.VldTag("tag2", p.VldBool())])
                             .validate(["true", "false"]),
                             p.ValidatorOK([("tag1", True), ("tag2", False)], processed=2))
        with self.subTest():
            self.assertEqual(p.VldMapDict(p.VldSeq([p.VldTag("tag1", p.VldBool()),
                                                    p.VldTag("tag2", p.VldBool())]))
                             .validate(["true", "false"]),
                             p.ValidatorOK({"tag1": True, "tag2": False}, processed=2))
        with self.subTest():
            self.assertEqual(p.VldMapDict(p.VldSeq([p.VldTag("tag1", p.VldBool().any()),
                                                    p.VldTag("tag2", p.VldAnyStr().any())]))
                             .validate(["true", "moi"]),
                             p.ValidatorOK({"tag1": True, "tag2": "moi"}, processed=2))

    def test_one_of(self) -> None:
        with self.subTest():
            self.assertEqual(p.VldOneOf([p.VldTag("tag1", p.VldBool().any()),
                                         p.VldTag("tag2", p.VldAnyStr().any())])
                             .validate(["moi"]),
                             p.ValidatorOK(("tag2", "moi"), processed=1))
        with self.subTest():
            self.assertEqual(p.VldOneOf([p.VldTag("tag1", p.VldBool().any()),
                                         p.VldTag("tag2", p.VldAnyStr().any())])
                             .validate(["true"]),
                             p.ValidatorOK(("tag1", True), processed=1))
        with self.subTest():
            self.assertEqual(p.VldOneOfStrings(["moi", "hei"])
                             .validate(["true"]),
                             p.ValidatorFail("Expected one of moi, hei"))
        with self.subTest():
            self.assertEqual(p.VldOneOfStrings(["moi", "hei"])
                             .validate(["moi"]),
                             p.ValidatorOK("moi", processed=1))
        with self.subTest():
            self.assertEqual(p.VldOneOfStrings(["moi", "hei"])
                             .validate(["hei"]),
                             p.ValidatorOK("hei", processed=1))

    def test_map_dict(self) -> None:
        with self.subTest():
            self.assertEqual(p.VldMapDict(p.VldSomeOf([p.VldTag("tag1", p.VldBool().any()),
                                                       p.VldTag("tag2", p.VldAnyStr().any())]))
                             .validate(["moi"]),
                             p.ValidatorOK({"tag2": "moi"}, processed=1))
        with self.subTest():
            self.assertEqual(p.VldMapDict(p.VldSomeOf([p.VldTag("tag1", p.VldBool().any()),
                                                       p.VldTag("tag2", p.VldAnyStr().any())]))
                             .validate(["true", "moi"]),
                             p.ValidatorOK({"tag1": True, "tag2": "moi"}, processed=2))

    def test_lambda(self) -> None:
        with self.subTest():
            def fixed() -> p.Validator[str]:
                return p.VldFixedStr("moi")
            self.assertEqual(p.VldDelayed(fixed).validate(["moi"]),
                             p.ValidatorOK("moi", processed=1))
