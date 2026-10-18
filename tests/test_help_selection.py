"""Verify command discovery, focused documents, and configurable presentation."""

import contextlib
import enum
import io
import pathlib
import unittest
from typing import Any

import argparsec as p
import argparsec.commands as c
import argparsec.help as h


class Section(enum.Enum):
    """Declare stable presentation groups for cross-section selection."""

    JOBS = "Jobs"
    SUBS = "Subscriptions"


class Explosive(p.Parser[str]):
    """Provide an opaque parser that exposes accidental semantic execution."""

    def parse(self, args: list[str]) -> p.ParseResult[str]:
        """Reject any attempt to execute the parser during documentation."""
        raise AssertionError("documentation invoked parsing")


def entry(usage: h.Usage, *, name: str | None = None) -> h.Entry:
    """Construct a resolved entry for adversarial scope-graph tests."""
    return h.Entry(usage, None, (), None, 0, h.Scope(), name)


class TestHelpSelection(unittest.TestCase):
    """Check selection and rendering independently of application policies."""

    def test_readme_example(self) -> None:
        """Execute the public README example and verify its focused output."""
        readme = pathlib.Path("README.md").read_text()
        example = (
            readme.split("## Focused Help", 1)[1]
            .split("```python\n", 1)[1]
            .split("```", 1)[0]
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(example, {})
        self.assertEqual(
            output.getvalue(),
            "notify TEXT | ping TEXT\n  Send a notification\n  e.g. ping hello\n",
        )

    def test_synonyms_multiple_entries_and_sections(self) -> None:
        """Select all matching heads, not modifiers, definitions, or section peers."""
        action = p.Meta(
            p.OneOfStrings(["ack", "snooze"]), mode="reference", name="action"
        )
        grammar = p.OneOf[Any](
            p.Meta(
                p.Keyword("cancel", p.Keyword("sub", p.AnyStr())),
                mode="entry",
                section=Section.SUBS,
            ),
            p.Meta(
                p.OneOf(p.Keyword("notify", p.AnyStr()), p.Keyword("ping", p.AnyStr())),
                mode="entry",
                description="Notify",
                examples=[("ping", "hello")],
                section=Section.JOBS,
            ),
            p.Meta(
                p.OneOfStrings(["cancel", "atrm"]),
                mode="entry",
                section=Section.JOBS,
                order=-1,
            ),
            p.Meta(p.Keyword("cancel", p.Int()), mode="entry", section=Section.JOBS),
            p.Meta(p.Keyword("at", action), mode="entry", section=Section.JOBS),
            p.Meta(
                p.Keyword("every", p.Keyword("until", action)),
                mode="entry",
                section=Section.JOBS,
            ),
            p.Meta(
                p.Keyword("kitchen", p.Keyword("timer", p.Int())),
                mode="entry",
                section=Section.JOBS,
            ),
        )
        document = p.Help[None]().document(grammar, None, section_order=[Section.SUBS])
        self.assertEqual(
            document.command_names(),
            {"cancel", "atrm", "notify", "ping", "at", "every", "kitchen"},
        )
        self.assertEqual(
            document.for_command("notify").render(),
            document.for_command("ping").render(),
        )
        self.assertIn("Notify", document.for_command("ping").render())
        self.assertIn("e.g. ping hello", document.for_command("ping").render())
        focused = document.for_command("cancel")
        self.assertEqual(len(focused.scope.entries), 3)
        self.assertEqual(focused.section_order, (Section.SUBS,))
        text = focused.render()
        self.assertLess(text.index("Subscriptions:"), text.index("Jobs:"))
        self.assertLess(text.index("cancel | atrm"), text.index("cancel 123"))
        self.assertNotIn("Notify", text)
        self.assertNotIn("<action>", text)
        self.assertIn("<action> =", document.for_command("at").render())
        self.assertNotIn("at <action>", document.for_command("every").render())
        self.assertEqual(document.for_command("missing").render(), "")
        self.assertEqual(document.for_command("Ping").render(), "")

    def test_strict_prefix_contract(self) -> None:
        """Reject unsupported and partly opaque prefixes rather than omit names."""
        invalid: list[h.Usage] = [
            h.Argument("COMMAND"),
            h.SequenceUsage(),
            h.Alternatives(()),
            h.OptionalUsage(h.Literal("maybe")),
            h.Repetition(h.Literal("repeat")),
            h.Unordered((h.Literal("any"),)),
            h.Reference("command", 1),
            h.SequenceUsage((h.SequenceUsage(), h.Literal("later"))),
            h.Alternatives((h.Literal("known"), h.Argument("unknown"))),
        ]
        for usage in invalid:
            with self.subTest(usage=usage):
                document = h.Document(h.Scope(entries=[entry(usage)]))
                with self.assertRaisesRegex(p.HelpError, "nonoptional literal prefix"):
                    document.command_names()
                with self.assertRaisesRegex(p.HelpError, "nonoptional literal prefix"):
                    document.for_command("known")
        usage = h.Annotation(
            h.SequenceUsage(
                (
                    h.Alternatives((h.Literal("Ping"), h.Literal("ping"))),
                    h.Argument("tail"),
                )
            ),
            "Note",
            (),
        )
        document = h.Document(h.Scope(entries=[entry(usage)]))
        self.assertEqual(document.command_names(), {"Ping", "ping"})
        self.assertEqual(h.Document(h.Scope()).command_names(), set())

    def test_selection_copies_and_prunes_recursive_graphs(self) -> None:
        """Keep reachable identities and recursion while isolating mutable model state."""
        shared = entry(
            h.Alternatives((h.Literal("end"), h.Reference("action", 1))), name="action"
        )
        shared.scope.definitions[1] = shared
        unused = entry(h.Literal("unused"), name="unused")
        parent = entry(h.SequenceUsage((h.Literal("run"), h.Reference("action", 1))))
        parent.scope.definitions.update({1: shared, 2: unused})
        parent.scope.annotations.append(
            h.Annotation(h.Literal("run"), "Scope note", ())
        )
        parent.scope.entries.append(entry(h.Literal("nested")))
        root = h.Scope(
            entries=[parent, entry(h.Literal("other"))],
            definitions={1: shared, 2: unused},
            annotations=[h.Annotation(h.Literal("run"), "Root note", ())],
        )
        document = h.Document(root)
        before = document.render()
        selected = document.for_command("run")
        copied = selected.scope.entries[0]
        self.assertEqual(set(selected.scope.definitions), {1})
        self.assertEqual(set(copied.scope.definitions), {1})
        definition = copied.scope.definitions[1]
        self.assertIs(definition.scope.definitions[1], definition)
        self.assertIs(selected.scope.definitions[1], definition)
        self.assertEqual(selected.render().count("<action> ="), 1)
        self.assertIn("Root note", selected.render())
        self.assertIn("Scope note", selected.render())
        self.assertIn("nested", selected.render())
        self.assertNotIn("unused", selected.render())
        copied.description = "Changed"
        copied.scope.entries.clear()
        definition.scope.definitions.clear()
        selected.scope.annotations.clear()
        self.assertEqual(document.render(), before)
        self.assertEqual(document.for_command("missing").scope.annotations, [])

    def test_selection_preserves_scope_collisions(self) -> None:
        """Keep same-name definitions distinct in separate relative scopes."""
        first = entry(h.SequenceUsage((h.Literal("run"), h.Reference("action", 1))))
        second = entry(h.SequenceUsage((h.Literal("run"), h.Reference("action", 2))))
        first.scope.definitions[1] = entry(h.Literal("start"), name="action")
        second.scope.definitions[2] = entry(h.Literal("stop"), name="action")
        selected = h.Document(h.Scope(entries=[first, second])).for_command("run")
        self.assertIn("<action> = start", selected.render())
        self.assertIn("<action> = stop", selected.render())
        with self.assertRaisesRegex(p.HelpError, "conflicting name"):
            selected.render(definition_layout="section")

    def test_visibility_contexts_and_no_extra_provider_evaluation(self) -> None:
        """Use visible resolved metadata only, with fresh state across requests."""
        renderer = p.Help[bool]()
        calls: list[str] = []

        def describe(admin: bool) -> str:
            """Record evaluations of secret-bearing metadata."""
            calls.append("description")
            return "Secret information"

        grammar = p.OneOf(
            p.Meta(p.Keyword("public", p.Empty()), mode="entry"),
            renderer.meta(
                p.Keyword("private", p.Empty()),
                mode="entry",
                visible=lambda admin: admin,
                description=describe,
                section=Section.SUBS,
            ),
        )
        public = renderer.document(grammar, False)
        self.assertEqual(public.command_names(), {"public"})
        self.assertEqual(public.for_command("private").render(), "")
        self.assertEqual(calls, [])
        private = renderer.document(grammar, True)
        self.assertEqual(private.command_names(), {"public", "private"})
        for _ in range(2):
            private.for_command("private").render(
                description_layout="below", definition_layout="section"
            )
        self.assertEqual(calls, ["description"])
        renderer.document(grammar, True, sections=[Section.JOBS])
        self.assertEqual(calls, ["description"])
        self.assertEqual(renderer.document(grammar, False).command_names(), {"public"})

    def test_no_semantic_callbacks_or_delayed_factories(self) -> None:
        """Discover opaque declared heads without parsing, validation, or mapping."""

        def forbidden(*args: object) -> str:
            """Fail if any semantic operation is called."""
            raise AssertionError("semantic callback invoked")

        opaque = p.Meta(
            Explosive(),
            usage=h.SequenceUsage((h.Literal("notify"), h.Argument("TEXT"))),
            examples=[],
        )
        grammar = p.Remaining(p.Map(forbidden, p.CaptureOnly(opaque)))
        document = p.Help[None]().document(grammar, None)
        self.assertEqual(document.command_names(), {"notify"})
        self.assertEqual(document.for_command("notify").render(), "notify TEXT")
        renderer = p.Help[None]()
        delayed = renderer.meta(
            p.Delayed(lambda: p.CaptureFixedStr(forbidden())),
            grammar=lambda _: p.Keyword("run", p.Empty()),
        )
        self.assertEqual(renderer.document(delayed, None).command_names(), {"run"})

    def test_live_registry_and_handler_safety(self) -> None:
        """Fresh documents see registrations while selected snapshots stay resolved."""

        async def forbidden(ctx: None, value: object) -> None:
            """Fail if help invokes a registered command handler."""
            raise AssertionError("handler invoked")

        registry = c.Commands[None]()
        registry.register(c.Function("Ping", "Ping", p.Empty(), forbidden))
        parser = registry.parser()
        renderer = p.Help[None]()
        old = renderer.document(parser, None)
        registry.register(c.Function("cancel", "Cancel", p.Int(), forbidden))
        fresh = renderer.document(parser, None)
        self.assertEqual(old.command_names(), {"Ping"})
        self.assertEqual(fresh.command_names(), {"Ping", "cancel"})
        self.assertEqual(fresh.for_command("Ping").scope.entries[0].description, "Ping")
        self.assertEqual(fresh.for_command("ping").render(), "")

    def test_render_options_and_defaults(self) -> None:
        """Preserve default text and offer separate descriptions and token formatting."""
        grammar = p.Meta(
            p.Keyword("say", p.AnyStr()),
            description="Send text",
            examples=[("say", "two words")],
        )
        renderer = p.Help[None]()
        document = renderer.document(grammar, None)
        self.assertEqual(
            document.render(), "say TEXT\n  say TEXT: Send text\n  e.g. say 'two words'"
        )
        declared = p.Meta(
            p.Keyword("say", p.AnyStr()),
            mode="entry",
            description="Send text",
            examples=[("say", "two words")],
        )
        options = renderer.document(declared, None).render(
            description_layout="below", example_formatter=" ".join
        )
        self.assertEqual(options, "say TEXT\n  Send text\n  e.g. say two words")
        self.assertEqual(
            renderer.render(
                declared, None, description_layout="below", example_formatter=" ".join
            ),
            options,
        )
        self.assertEqual(
            p.render_help(
                declared, description_layout="below", example_formatter=" ".join
            ),
            options,
        )
        suppressed = renderer.document(
            p.Meta(p.Keyword("say", p.AnyStr()), mode="entry", examples=[]), None
        )
        self.assertNotIn("e.g.", suppressed.for_command("say").render())

    def test_section_definitions_and_inherited_headings(self) -> None:
        """Share definitions per section while preserving nested metadata and order."""
        action = p.Meta(
            p.OneOf(
                p.Meta(p.OneOfStrings(["start", "stop"]), mode="entry", examples=[])
            ),
            mode="reference",
            name="action",
            examples=[],
        )
        grammar = p.OneOf(
            p.Meta(
                p.Keyword("run", action),
                mode="entry",
                section=Section.JOBS,
                examples=[],
            ),
            p.Meta(
                p.Keyword("run", action),
                mode="entry",
                section=Section.JOBS,
                examples=[],
            ),
            p.Meta(
                p.Keyword("run", action),
                mode="entry",
                section=Section.SUBS,
                examples=[],
            ),
        )
        document = p.Help[None]().document(grammar, None)
        before = document.render()
        self.assertEqual(before.count("<action> ="), 3)
        text = document.render(
            definition_layout="section", repeat_section_headings=False
        )
        self.assertEqual(text.count("<action> ="), 2)
        self.assertEqual(text.count("Jobs:"), 1)
        self.assertEqual(text.count("Subscriptions:"), 1)
        self.assertEqual(text.count("start | stop"), 4)
        self.assertEqual(document.render(), before)
        self.assertEqual(
            document.for_command("run").render(
                definition_layout="section", repeat_section_headings=False
            ),
            text,
        )

    def test_hoisting_rejects_scope_dependent_identity(self) -> None:
        """Do not conflate one identity with different resolved relative definitions."""
        first = entry(h.SequenceUsage((h.Literal("run"), h.Reference("action", 1))))
        second = entry(first.usage)
        first.scope.definitions[1] = entry(h.Literal("start"), name="action")
        second.scope.definitions[1] = entry(h.Literal("stop"), name="action")
        document = h.Document(h.Scope(entries=[first, second]))
        with self.assertRaisesRegex(p.HelpError, "different relative scopes"):
            document.render(definition_layout="section")
        self.assertEqual(document.render().count("<action> ="), 2)

    def test_hoisting_keeps_relative_child_definitions(self) -> None:
        """Keep a child's scope-specific definition even if its identity is hoisted outside."""
        outer = entry(h.Literal("outer"), name="action")
        wrapper = entry(h.Reference("action", 1), name="wrapper")
        wrapper.scope.definitions[1] = entry(h.Literal("inner"), name="action")
        parent = entry(
            h.SequenceUsage(
                (h.Literal("run"), h.Reference("action", 1), h.Reference("wrapper", 2))
            )
        )
        parent.scope.definitions.update({1: outer, 2: wrapper})
        selected = h.Document(h.Scope(entries=[parent])).for_command("run")
        text = selected.render(definition_layout="section")
        self.assertIn("<action> = outer", text)
        self.assertIn("  <action> = inner", text)
        self.assertEqual(text.count("<action> ="), 2)

    def test_example_formatter_applies_to_group_notes(self) -> None:
        """Format scope examples without discarding notes or overriding suppression."""
        parent = entry(h.Literal("run"))
        parent.scope.annotations.append(
            h.Annotation(h.Literal("run"), "Child note", (("two words",),))
        )
        document = h.Document(
            h.Scope(
                entries=[parent],
                annotations=[
                    h.Annotation(h.Literal("run"), "Root note", (("run", "two words"),))
                ],
            )
        )
        text = document.for_command("run").render(example_formatter=" ".join)
        self.assertIn("Root note\n  e.g. run two words", text)
        self.assertIn("Child note\n    e.g. two words", text)

    def test_named_recursive_parser_selection_and_hoisting(self) -> None:
        """Terminate recursive provider-built grammars without reevaluating providers."""
        renderer = p.Help[None]()
        calls: list[str] = []

        def grammar(ctx: None) -> p.Parser[str]:
            """Build a structurally recursive help grammar once per document."""
            calls.append("grammar")
            return p.OneOf(p.CaptureFixedStr("end"), p.Keyword("next", recursive))

        recursive = renderer.meta(
            p.Delayed(lambda: Explosive()),
            mode="reference",
            name="action",
            grammar=grammar,
            examples=[],
        )
        parser = p.OneOf(
            p.Meta(p.Keyword("run", recursive), mode="entry", examples=[]),
            p.Meta(p.Keyword("run", recursive), mode="entry", examples=[]),
        )
        document = renderer.document(parser, None)
        text = document.for_command("run").render(definition_layout="section")
        self.assertEqual(text.count("<action> ="), 1)
        self.assertIn("next <action>", text)
        self.assertEqual(calls, ["grammar"])
