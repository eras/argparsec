"""Exercise generated grammar help independently of consuming applications."""

import dataclasses
import enum
import pathlib
import subprocess
import sys
import unittest

import argparsec as p
import argparsec.commands as c
import argparsec.help as h


class Section(enum.Enum):
    """Declare presentation order independently of grammar order."""

    GENERAL = "General"
    SCHEDULE = "Scheduling"
    ADMIN = "Admin"


@dataclasses.dataclass
class Context:
    """Supply help-specific cached data and permissions."""

    vehicle: str
    admin: bool = False


class Opaque(p.Parser[str]):
    """Represent a custom leaf whose syntax cannot be inferred from Python."""

    def parse(self, args: list[str]) -> p.ParseResult[str]:
        """Fail loudly if documentation accidentally executes parsing."""
        raise AssertionError("parse must not execute")


class TestHelp(unittest.TestCase):
    """Verify syntax, scopes, lazy metadata, and safe documentation traversal."""

    def test_root_registry_group_metadata(self) -> None:
        """GH-ASTRA-06: retain root metadata across wrappers and section selection."""

        async def handler(ctx: None, value: object) -> None:
            """Supply an inert executable command for help generation."""
            pass

        registry = c.Commands[None]()
        registry.register(
            c.Function(
                "info",
                "Information",
                p.Meta(
                    p.Optional(p.Keyword("detail", p.Empty())), section=Section.GENERAL
                ),
                handler,
            )
        )
        registry.register(
            c.Function(
                "secret", "Private", p.Meta(p.Empty(), section=Section.ADMIN), handler
            )
        )
        renderer = p.Help[None]()
        calls: list[str] = []

        def describe(ctx: None) -> str:
            """Track each request's group description evaluation."""
            calls.append("description")
            return "Registry-wide guidance"

        def examples(ctx: None) -> h.Examples:
            """Provide complete command examples at the root grouping boundary."""
            calls.append("examples")
            return [("info", "detail")]

        for parser in (registry.parser(), p.Remaining(registry.parser())):
            static = p.Meta(parser, description="Static guidance", examples=[("info",)])
            text = p.render_help(p.Remaining(static), sections=[Section.GENERAL])
            self.assertIn("Static guidance", text)
            self.assertIn("info", text)
            self.assertNotIn("secret", text)
            lazy = renderer.meta(parser, description=describe, examples=examples)
            calls.clear()
            document = renderer.document(
                p.Remaining(lazy), None, sections=[Section.GENERAL]
            )
            text = document.render()
            self.assertIn("Registry-wide guidance", text)
            self.assertIn("e.g. info detail", text)
            self.assertNotIn("secret", text)
            self.assertEqual(
                document.scope.annotations[0].examples, (("info", "detail"),)
            )
            self.assertEqual(document.render(), text)
            self.assertEqual(calls, ["description", "examples"])
            calls.clear()
            self.assertEqual(
                renderer.render(lazy, None, sections=[Section.SCHEDULE]), ""
            )
            self.assertEqual(calls, [])
        suppressed = renderer.document(p.Meta(registry.parser(), examples=[]), None)
        self.assertEqual(suppressed.scope.annotations[0].examples, ())

        hidden = c.Commands[None]()
        hidden.register(
            c.Function(
                "info",
                "Information",
                renderer.meta(p.Empty(), visible=lambda _: False),
                handler,
            )
        )
        calls.clear()
        self.assertEqual(
            renderer.render(
                renderer.meta(hidden.parser(), description=describe, examples=examples),
                None,
            ),
            "",
        )
        self.assertEqual(calls, [])

    def test_root_registry_provider_failure_is_located(self) -> None:
        """GH-ASTRA-06: root descriptions and examples preserve provider diagnostics."""

        async def handler(ctx: None, value: object) -> None:
            """Supply a command whose handler must not run during rendering."""
            pass

        failure = RuntimeError("guidance unavailable")

        def broken_description(ctx: None) -> str:
            """Raise a recognizable provider error for cause verification."""
            raise failure

        def broken_examples(ctx: None) -> h.Examples:
            """Verify collection providers also use located error handling."""
            raise failure

        renderer = p.Help[None]()
        registry = c.Commands[None]()
        registry.register(c.Function("info", "Information", p.Empty(), handler))
        for field, parser in (
            (
                "description",
                renderer.meta(registry.parser(), description=broken_description),
            ),
            ("examples", renderer.meta(registry.parser(), examples=broken_examples)),
        ):
            with self.assertRaisesRegex(
                p.HelpError, rf"root/item/inline\.{field}: guidance unavailable"
            ) as caught:
                renderer.render(p.Remaining(parser), None)
            self.assertIs(caught.exception.__cause__, failure)

    def test_singleton_choices_preserve_repeated_item_boundaries(self) -> None:
        """GH-ASTRA-01: propagate precedence through equivalent singleton nodes."""
        item = p.Keyword("at", p.HhMm())
        for equivalent in (item, p.OneOf(item), p.OneOf(p.Seq([p.OneOf(item)]))):
            self.assertEqual(self.usage(p.List(equivalent)), "[(at hh:mm) ...]")
            self.assertEqual(
                self.usage(p.Separated(equivalent, "and")),
                "(at hh:mm) [and (at hh:mm) ...]",
            )
        choice = p.OneOf(p.OneOfStrings(["start", "stop"]))
        self.assertEqual(
            self.usage(p.Keyword("run", p.Seq([choice]))), "run (start | stop)"
        )

    def test_transparent_root_registry_scopes(self) -> None:
        """GH-ASTRA-02: wrappers preserve root filtering and section inheritance."""

        async def handler(ctx: None, value: object) -> None:
            """Provide an inert registry handler for documentation tests."""
            pass

        registry = c.Commands[None]()
        registry.register(
            c.Function(
                "info", "Public", p.Meta(p.Empty(), section=Section.GENERAL), handler
            )
        )
        registry.register(
            c.Function(
                "secret", "Private", p.Meta(p.Empty(), section=Section.ADMIN), handler
            )
        )
        registry.register(c.Function("inherited", "Inherited", p.Empty(), handler))
        root = registry.parser()
        for wrapped in (p.Meta(root), p.Remaining(root)):
            self.assertEqual(p.render_help(wrapped), p.render_help(root))
        for selected, included, excluded in (
            (Section.GENERAL, "info", "secret"),
            (Section.ADMIN, "secret", "info"),
        ):
            expected = p.render_help(root, sections=[selected])
            for wrapped in (
                p.Meta(root),
                p.Remaining(root),
                p.Meta(p.Remaining(p.Meta(root))),
            ):
                text = p.render_help(wrapped, sections=[selected])
                self.assertEqual(text, expected)
                self.assertIn(included, text)
                self.assertNotIn(excluded, text)
            inherited = p.Meta(p.Remaining(root), section=selected)
            text = p.render_help(inherited, sections=[selected])
            self.assertIn(included, text)
            self.assertIn("inherited", text)
            self.assertNotIn(excluded, text)
        nested = p.Meta(p.Keyword("set", root), mode="entry", section=Section.GENERAL)
        text = p.render_help(nested, sections=[Section.GENERAL])
        self.assertIn("set <command>", text)
        self.assertIn("secret", text)

    def test_rejected_sequences_discard_scope_contributions(self) -> None:
        """GH-ASTRA-03: rejected required branches cannot publish entries or definitions."""
        renderer = p.Help[None]()
        hidden = renderer.meta(p.Int(), visible=lambda _: False)
        reference = p.Meta(
            p.CaptureFixedStr("secret"), mode="reference", name="rejected"
        )
        entry = p.Meta(p.CaptureFixedStr("leaked"), mode="entry")
        visible = p.Adjacent(entry, reference)
        for before in (True, False):
            parts = (
                [visible.any(), hidden.any()]
                if before
                else [hidden.any(), visible.any()]
            )
            for rejected in (p.Adjacent(parts[0], parts[1]), p.Seq(parts)):
                document = renderer.document(rejected, None)
                self.assertEqual(document.render(), "")
                self.assertEqual(document.scope.entries, [])
                self.assertEqual(document.scope.definitions, {})
                survivor = p.Meta(p.CaptureFixedStr("survivor"), mode="entry")
                for alternatives in (
                    (rejected.any(), survivor.any()),
                    (survivor.any(), rejected.any()),
                ):
                    text = renderer.render(p.OneOf(*alternatives), None)
                    self.assertIn("survivor", text)
                    self.assertNotIn("leaked", text)
                    self.assertNotIn("rejected", text)
                    self.assertNotIn("secret", text)

    def test_hidden_unordered_options_preserve_commands(self) -> None:
        """GH-ASTRA-04: an empty visible optional set is zero-token syntax."""
        renderer = p.Help[None]()
        hidden = renderer.meta(p.Int(), visible=lambda _: False)

        async def handler(ctx: None, value: object) -> None:
            """Provide a registry boundary without executing any command."""
            pass

        for options in (
            p.SomeOf(hidden).any(),
            p.SomeOf2(hidden, hidden).any(),
            p.SomeOf3(hidden, hidden, hidden).any(),
            p.SomeOf4(hidden, hidden, hidden, hidden).any(),
        ):
            grammar = p.Keyword("run", options)
            document = renderer.document(grammar, None)
            self.assertEqual(h.format_usage(document.scope.entries[0].usage), "run")
            sequence = p.Adjacent(p.CaptureFixedStr("run"), options)
            document = renderer.document(sequence, None)
            self.assertEqual(h.format_usage(document.scope.entries[0].usage), "run")
            registry = c.Commands[None]()
            registry.register(c.Function("run", "Run", options, handler))
            self.assertIn("run: Run", registry.help(None, renderer=renderer))
        options = p.SomeOf(p.Meta(p.Keyword("count", p.Int())), hidden)
        partial = p.Adjacent(p.CaptureFixedStr("run"), options)
        text = renderer.render(partial, None)
        self.assertIn("run {count 123} (optional, any order)", text)
        self.assertNotIn(";", text)
        registry = c.Commands[None]()
        registry.register(c.Function("run", "Run", options, handler))
        self.assertIn(
            "run {count 123} (optional, any order): Run",
            registry.help(None, renderer=renderer),
        )

    def test_shared_references_inherit_each_parent_scope(self) -> None:
        """GH-ASTRA-05: definitions are scope-local while provider values stay shared."""
        renderer = p.Help[None]()
        calls: list[str] = []

        def description(ctx: None) -> str:
            """Count shared provider evaluations independently of definition construction."""
            calls.append("description")
            return "Value"

        shared = renderer.meta(
            p.Meta(p.Int(), mode="entry"),
            mode="reference",
            name="value",
            description=description,
        )
        for sections in (
            (Section.GENERAL, Section.ADMIN),
            (Section.ADMIN, Section.GENERAL),
        ):
            calls.clear()
            grammar = p.OneOf(
                *(
                    p.Meta(p.Adjacent(shared, shared), mode="entry", section=section)
                    for section in sections
                )
            )
            document = renderer.document(grammar, None)
            self.assertEqual(calls, ["description"])
            definitions = []
            for parent, section in zip(document.scope.entries, sections):
                self.assertEqual(len(parent.scope.definitions), 1)
                definition = parent.scope.definitions[id(shared)]
                definitions.append(definition)
                self.assertEqual(definition.section, section)
                self.assertEqual(definition.scope.entries[0].section, section)
            self.assertIsNot(definitions[0], definitions[1])
            self.assertEqual(document.render().count("<value> ="), 2)

    def usage[T](self, parser: p.Parser[T]) -> str:
        """Get just the root syntax from a context-free resolved model."""
        return h.format_usage(
            h.Help[None]().document(parser, None).scope.entries[0].usage
        )

    def test_precedence_and_structural_examples(self) -> None:
        """Group choices and multi-token repeated items without changing their grammar."""
        item = p.OneOf(p.Keyword("limit", p.Int()), p.Keyword("speed", p.Int()))
        grammar = p.Remaining(p.Separated(item, "and"))
        self.assertEqual(
            self.usage(grammar),
            "(limit 123 | speed 123) [and (limit 123 | speed 123) ...]",
        )
        self.assertEqual(
            self.usage(p.List(p.Adjacent(p.Int(), p.HhMm()))), "[(123 hh:mm) ...]"
        )
        self.assertEqual(
            self.usage(p.Optional(p.Keyword("at", p.HhMm()))), "[at hh:mm]"
        )
        document = h.Help[None]().document(grammar, None)
        for example in document.scope.entries[0].examples:
            self.assertIsInstance(grammar.parse(list(example)), p.ParseOK)

    def test_metadata_defaults_are_independent(self) -> None:
        """Usage labels preserve built-in examples; explicit empty examples suppress them."""
        renderer = h.Help[None]()
        default = renderer.document(
            p.Meta(p.Int(), usage="COUNT", description="Unsigned count"), None
        )
        self.assertEqual(default.scope.entries[0].examples, (("123",),))
        self.assertIn("COUNT: Unsigned count", default.render())
        self.assertNotIn("e.g.", p.render_help(p.Meta(p.Int(), examples=[])))
        self.assertEqual(
            self.usage(p.Adjacent(p.CaptureFixedStr("info"), p.Empty())), "info"
        )
        self.assertIn("hh:mm", p.render_help(p.HhMm()))

    def test_opaque_and_composite_override_boundaries(self) -> None:
        """Require explicit opaque syntax and reject replacing known composite grammars."""
        with self.assertRaisesRegex(p.HelpError, "root/left.*Opaque"):
            p.render_help(p.Adjacent(Opaque(), p.Empty()))
        grammar = p.Meta(
            Opaque(),
            usage=h.SequenceUsage((h.Literal("local"), h.Argument("TIME"))),
            examples=[("local", "12:30")],
        )
        self.assertIn("local TIME", p.render_help(grammar))
        with self.assertRaisesRegex(p.HelpError, "composite"):
            p.render_help(p.Meta(p.Keyword("at", p.HhMm()), usage="anything"))

    def test_callbacks_and_delayed_are_not_executed(self) -> None:
        """Mappings, callbacks, conditions, and implicit factories stay dormant."""

        def fail(*args: object) -> str:
            """Detect accidental callback invocation during help generation."""
            raise AssertionError("callback executed")

        def callback(args: str) -> None:
            """Detect accidental execution of a deferred callback."""
            raise AssertionError("callback executed")

        wrapped = p.Remaining(p.CaptureOnly(p.Callback(callback, p.Map(fail, p.Int()))))
        self.assertEqual(self.usage(wrapped), "123")
        delayed = p.Delayed(lambda: Opaque())
        with self.assertRaisesRegex(p.HelpError, "Delayed"):
            p.render_help(delayed)
        renderer = p.Help[Context]()
        documented = renderer.meta(
            delayed, grammar=lambda ctx: p.OneOfStrings([ctx.vehicle])
        )
        self.assertIn("Roadster", renderer.render(documented, Context("Roadster")))
        conditional = p.Conditional(lambda: bool(fail()), p.Int())
        with self.assertRaisesRegex(p.HelpError, "Conditional"):
            p.render_help(conditional)
        visible = renderer.meta(conditional, visible=lambda ctx: ctx.admin)
        self.assertEqual(renderer.render(visible, Context("x")), "")
        self.assertIn("123", renderer.render(visible, Context("x", True)))

    def test_provider_once_and_errors_and_ownership(self) -> None:
        """Cache fields only within a render and locate failures before unsafe context use."""
        renderer = p.Help[Context]()
        calls: list[str] = []

        def label(ctx: Context) -> str:
            """Record one usage-provider evaluation."""
            calls.append(ctx.vehicle)
            return ctx.vehicle

        def examples(ctx: Context) -> h.Examples:
            """Record collection evaluation and return complete token sequences."""
            calls.append("examples")
            return [(ctx.vehicle, "two words")]

        def broken(ctx: Context) -> str:
            """Produce a provider failure with a field-specific location."""
            raise RuntimeError("cache unavailable")

        leaf = renderer.meta(Opaque(), usage=label, examples=examples)
        grammar = p.OneOf(leaf, leaf)
        text = renderer.render(grammar, Context("A"))
        self.assertIn("A 'two words'", text)
        self.assertEqual(calls, ["A", "examples"])
        renderer.render(grammar, Context("B"))
        self.assertEqual(calls, ["A", "examples", "B", "examples"])
        with self.assertRaisesRegex(p.HelpError, "another Help"):
            p.Help[str]().render(grammar, "wrong")
        with self.assertRaisesRegex(
            p.HelpError, "root/inline.description: cache unavailable"
        ):
            renderer.render(renderer.meta(p.Int(), description=broken), Context("x"))

    def test_sections_filters_order_and_reference_reachability(self) -> None:
        """Honor Enum order, stable explicit ties, overrides, and retained references only."""
        shared = p.Meta(p.Keyword("start", p.Empty()), mode="reference", name="action")
        private = p.Meta(p.CaptureFixedStr("secret"), mode="reference", name="private")
        grammar = p.Meta(
            p.OneOf(
                p.Meta(private, mode="entry", section=Section.ADMIN),
                p.Meta(shared, mode="entry", section=Section.SCHEDULE, order=1),
                p.Meta(
                    p.CaptureFixedStr("first"), mode="entry", section=Section.GENERAL
                ),
                p.Meta(
                    p.CaptureFixedStr("second"), mode="entry", section=Section.GENERAL
                ),
            ),
            section=Section.SCHEDULE,
        )
        text = p.render_help(grammar)
        self.assertLess(text.index("General:"), text.index("Scheduling:"))
        self.assertLess(text.index("first"), text.index("second"))
        self.assertLess(text.index("Scheduling:"), text.index("Admin:"))
        filtered = p.render_help(grammar, sections=[Section.SCHEDULE])
        self.assertIn("<action> = start", filtered)
        self.assertNotIn("private", filtered)
        self.assertNotIn("General", filtered)
        explicit = p.render_help(grammar, section_order=[Section.ADMIN])
        self.assertTrue(explicit.startswith("Admin:"))
        self.assertEqual(p.render_help(grammar, sections=[]), "")

    def test_named_identity_variants_and_cycles(self) -> None:
        """Preserve same-name restricted variants and terminate named recursive grammar."""
        renderer = p.Help[None]()
        restricted = p.Meta(p.OneOfStrings(["start"]), mode="reference", name="action")
        broad = p.Meta(
            p.OneOfStrings(["start", "stop"]), mode="reference", name="action"
        )
        text = p.render_help(p.Adjacent(restricted, broad))
        self.assertEqual(text.count("<action> ="), 2)
        shared = p.render_help(p.Adjacent(restricted, restricted))
        self.assertEqual(shared.count("<action> ="), 1)
        recursive: p.Meta[str]
        delayed: p.Delayed[str] = p.Delayed(lambda: recursive)
        recursive = renderer.meta(
            delayed,
            mode="reference",
            name="tree",
            grammar=lambda _: p.OneOf(
                p.CaptureFixedStr("leaf"), p.Keyword("branch", recursive)
            ),
        )
        text = renderer.render(recursive, None)
        self.assertEqual(text.count("<tree> ="), 1)
        self.assertIn("leaf | branch <tree>", text)
        unnamed = p.Meta(p.CaptureFixedStr("leaf"))
        unnamed.parser = unnamed
        with self.assertRaisesRegex(p.HelpError, "recursive grammar requires"):
            p.render_help(unnamed)

    def test_root_section_and_referenced_subordinate_entries(self) -> None:
        """Apply root sections while retaining definitions outside a selected section."""
        leaf = p.Meta(p.Int(), section=Section.GENERAL)
        self.assertTrue(p.render_help(leaf).startswith("General:"))
        self.assertEqual(p.render_help(leaf, sections=[Section.ADMIN]), "")
        definition = p.Meta(
            p.Meta(p.CaptureFixedStr("start"), mode="entry", section=Section.ADMIN),
            mode="reference",
            name="action",
        )
        grammar = p.Meta(definition, mode="entry", section=Section.GENERAL)
        text = p.render_help(grammar, sections=[Section.GENERAL])
        self.assertIn("<action> = start", text)
        self.assertIn("Admin:", text)
        self.assertIn("start", text)

    def test_builtin_leaf_examples_and_empty(self) -> None:
        """Keep complete token examples for suffix built-ins and omit empty syntax."""
        for parser in (
            p.PosIntSuffix(["h", "m"]),
            p.PosFloatSuffix(["km"]),
            p.Meters(),
        ):
            document = h.Help[None]().document(parser, None)
            for example in document.scope.entries[0].examples:
                self.assertIsInstance(parser.parse(list(example)), p.ParseOK)
        self.assertEqual(p.render_help(p.Empty()), "")

    def test_presentation_sorting_does_not_reorder_parsing(self) -> None:
        """Keep first-success execution priority despite explicit display ordering."""
        first = p.Meta(
            p.Map(lambda _: "first", p.Int()),
            mode="entry",
            order=10,
            description="first",
        )
        second = p.Meta(
            p.Map(lambda _: "second", p.Int()),
            mode="entry",
            order=-1,
            description="second",
        )
        grammar = p.OneOf(first, second)
        text = p.render_help(grammar)
        self.assertLess(text.index("second"), text.index("first"))
        result = grammar.parse(["123"])
        self.assertIsInstance(result, p.ParseOK)
        assert isinstance(result, p.ParseOK)
        self.assertEqual(result.value, "first")

    def test_live_nested_registry_and_distinct_contexts(self) -> None:
        """Read current nested registrations without executing dispatch handlers."""

        async def handler(ctx: int, value: object) -> None:
            """Detect invocation during documentation."""
            raise AssertionError("handler executed")

        renderer = p.Help[Context]()
        nested = c.Commands[int]()
        outer = c.Commands[int]()
        outer.register(c.Function("set", "Settings", nested.parser(), handler))
        nested.register(
            c.Function(
                "limit",
                "Count",
                renderer.meta(p.Int(), description=lambda ctx: ctx.vehicle),
                handler,
            )
        )
        first = outer.help(Context("Roadster"), renderer=renderer)
        self.assertIn("set <command>", first)
        self.assertIn("limit 123", first)
        self.assertIn("Roadster", first)
        nested.register(c.Function("info", "Information", p.Empty(), handler))
        self.assertIn("info: Information", outer.help(Context("S"), renderer=renderer))
        self.assertNotIn("info: Information", first)

    def test_scheduler_allowlist_and_optional_keyword(self) -> None:
        """Model scheduler variants structurally instead of exposing a global registry."""
        action = p.Meta(
            p.OneOf(
                p.CaptureFixedStr("info"),
                p.Keyword("climate", p.OneOfStrings(["on", "off"])),
            ),
            mode="reference",
            name="schedulable",
        )
        sequence = p.Separated(p.CaptureOnly(action), "and")
        grammar = p.Keyword(
            "at",
            p.Adjacent(p.HhMm(), p.OneOf(p.Keyword("sequence", sequence), sequence)),
        )
        text = p.render_help(grammar)
        self.assertIn("sequence", text)
        self.assertIn("[and <schedulable> ...]", text)
        self.assertIn("info | climate (on | off)", text)
        self.assertNotIn("logout", text)
        self.assertIsInstance(
            grammar.parse(["at", "12:30", "sequence", "info", "and", "climate", "on"]),
            p.ParseOK,
        )

    def test_context_typing_accepts_and_rejects(self) -> None:
        """Check provider contravariance and reject incompatible contexts using mypy."""
        root = pathlib.Path(__file__).resolve().parents[1]
        directory = root / "tmp" / "help-typing"
        directory.mkdir(parents=True, exist_ok=True)
        source = directory / "contexts.py"
        good = '''import argparsec as p
class Base:
    """Base rendering context."""
    pass

class Child(Base):
    """Narrow rendering context."""
    pass

def describe(ctx: Base) -> str:
    """Accept a broader context than the renderer requires."""
    return "description"

renderer = p.Help[Child]()
grammar = renderer.meta(p.Int(), description=describe)
renderer.render(p.Keyword("n", grammar), Child())
'''
        source.write_text(good)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "mypy",
                "--cache-dir",
                str(directory / "cache"),
                str(source),
            ],
            cwd=root,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        source.write_text(
            good
            + "\nrenderer.render(grammar, Base())\nrenderer.meta(p.Int(), description=lambda ctx: ctx.missing)\n"
        )
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "mypy",
                "--cache-dir",
                str(directory / "cache"),
                str(source),
            ],
            cwd=root,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("incompatible type", result.stdout)
        self.assertIn('has no attribute "missing"', result.stdout)
