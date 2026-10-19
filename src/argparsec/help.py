"""Structured, callback-free grammar documentation with request-local metadata."""

import dataclasses
import enum
import itertools
import shlex
from collections.abc import Callable, Sequence
from typing import Any, Literal as Mode, cast

from . import parser as p


@dataclasses.dataclass(frozen=True)
class Literal:
    """One fixed input token."""

    text: str


@dataclasses.dataclass(frozen=True)
class Argument:
    """An opaque argument label and optional complete example token sequence."""

    label: str
    example: tuple[str, ...] | None = None


@dataclasses.dataclass(frozen=True)
class SequenceUsage:
    """Consecutive grammar components; an empty sequence consumes no tokens."""

    items: tuple["Usage", ...] = ()


@dataclasses.dataclass(frozen=True)
class Alternatives:
    """Ordered choices; an empty collection has no accepted syntax."""

    items: tuple["Usage", ...]


@dataclasses.dataclass(frozen=True)
class OptionalUsage:
    """A component that can be omitted."""

    item: "Usage"


@dataclasses.dataclass(frozen=True)
class Repetition:
    """Zero-or-more items, or a nonempty separator-delimited sequence."""

    item: "Usage"
    separator: str | None = None


@dataclasses.dataclass(frozen=True)
class Unordered:
    """Optional components accepted in any order, each at most once."""

    items: tuple["Usage", ...]


@dataclasses.dataclass(frozen=True)
class Reference:
    """A named definition, resolved by identity rather than its display name."""

    name: str
    identity: int


@dataclasses.dataclass(frozen=True)
class Annotation:
    """Attach independent inline prose and examples to structured syntax."""

    item: "Usage"
    description: str | None
    examples: tuple[tuple[str, ...], ...] | None


type Usage = Literal | Argument | SequenceUsage | Alternatives | OptionalUsage | Repetition | Unordered | Reference | Annotation

type Examples = Sequence[tuple[str, ...]]

type Value[C, T] = T | Callable[[C], T]


class HelpError(ValueError):
    """Report missing metadata or provider failure at a grammar location."""


@dataclasses.dataclass
class _Spec:
    """Store erased providers behind a renderer ownership boundary."""

    owner: object | None = None
    mode: Mode["inline", "entry", "reference"] = "inline"
    name: str | None = None
    usage: Value[Any, Usage | str] | None = None
    examples: Value[Any, Examples] | None = None
    description: Value[Any, str] | None = None
    visible: Callable[[Any], bool] | None = None
    grammar: Callable[[Any], p.Parser[Any]] | None = None
    section: enum.Enum | None = None
    order: int = 0


class Meta[T](p.Parser[T]):
    """Attach context-free presentation without changing parsing or consumption.

    Use Help.meta for context-dependent providers. A usage override is an
    explicit declaration for an opaque leaf, never a replacement for a known
    executable combinator. A grammar provider explicitly opts into help-time
    grammar construction for Delayed parsers.
    """

    def __init__(
        self,
        parser: p.Parser[T],
        *,
        mode: Mode["inline", "entry", "reference"] = "inline",
        name: str | None = None,
        usage: Usage | str | None = None,
        examples: Examples | None = None,
        description: str | None = None,
        section: enum.Enum | None = None,
        order: int = 0,
    ) -> None:
        """Retain the executable parser and independent static metadata fields."""
        if mode == "reference" and not name:
            raise ValueError("reference metadata requires a name")
        self.parser = parser
        self._spec = _Spec(
            mode=mode,
            name=name,
            usage=usage,
            examples=examples,
            description=description,
            section=section,
            order=order,
        )

    def parse(self, args: list[str]) -> p.ParseResult[T]:
        """Delegate unchanged, without evaluating presentation metadata."""
        return self.parser.parse(args)


class Help[C]:
    """Own providers for one unbounded application-defined rendering context.

    Parsers remain context-free in their type signatures. Contextual Meta
    instances must be rendered by their creating Help instance; this checked
    ownership boundary prevents erasing context types through combinators.
    """

    def meta[T](
        self,
        parser: p.Parser[T],
        *,
        mode: Mode["inline", "entry", "reference"] = "inline",
        name: str | None = None,
        usage: Value[C, Usage | str] | None = None,
        examples: Value[C, Examples] | None = None,
        description: Value[C, str] | None = None,
        visible: Callable[[C], bool] | None = None,
        grammar: Callable[[C], p.Parser[Any]] | None = None,
        section: enum.Enum | None = None,
        order: int = 0,
    ) -> Meta[T]:
        """Bind lazy fields to this renderer, preserving the parser result type."""
        result = Meta(parser, mode=mode, name=name)
        result._spec = _Spec(
            self,
            mode,
            name,
            usage,
            examples,
            description,
            visible,
            grammar,
            section,
            order,
        )
        return result

    def document(
        self,
        parser: p.Parser[Any],
        context: C,
        *,
        sections: Sequence[enum.Enum] | None = None,
        section_order: Sequence[enum.Enum] | None = None,
    ) -> "Document":
        """Resolve providers once in a fresh traversal, without invoking parsers."""
        return _Build(self, context, sections, section_order).document(parser)

    def render(
        self,
        parser: p.Parser[Any],
        context: C,
        *,
        sections: Sequence[enum.Enum] | None = None,
        section_order: Sequence[enum.Enum] | None = None,
        description_layout: Mode["inline", "below"] = "inline",
        definition_layout: Mode["entry", "section"] = "entry",
        repeat_section_headings: bool = True,
        example_formatter: Callable[[Sequence[str]], str] = shlex.join,
    ) -> str:
        """Render one request; no provider results survive between requests."""
        return self.document(
            parser, context, sections=sections, section_order=section_order
        ).render(
            description_layout=description_layout,
            definition_layout=definition_layout,
            repeat_section_headings=repeat_section_headings,
            example_formatter=example_formatter,
        )


def render_help(
    parser: p.Parser[Any],
    *,
    sections: Sequence[enum.Enum] | None = None,
    section_order: Sequence[enum.Enum] | None = None,
    description_layout: Mode["inline", "below"] = "inline",
    definition_layout: Mode["entry", "section"] = "entry",
    repeat_section_headings: bool = True,
    example_formatter: Callable[[Sequence[str]], str] = shlex.join,
) -> str:
    """Render context-free metadata; contextual wrappers require their owner."""
    return Help[None]().render(
        parser,
        None,
        sections=sections,
        section_order=section_order,
        description_layout=description_layout,
        definition_layout=definition_layout,
        repeat_section_headings=repeat_section_headings,
        example_formatter=example_formatter,
    )


def format_usage(usage: Usage, precedence: int = 0) -> str:
    """Format syntax with grouping that preserves alternatives and item boundaries."""
    match usage:
        case Annotation(item):
            return format_usage(item, precedence)
        case Literal(text):
            return shlex.quote(text)
        case Argument(label):
            return label
        case Reference(name):
            return f"<{name}>"
        case SequenceUsage(items):
            if len(items) == 1:
                return format_usage(items[0], precedence)
            text = " ".join(filter(None, (format_usage(x, 2) for x in items)))
            return f"({text})" if precedence > 2 and len(items) > 1 else text
        case Alternatives(items):
            if len(items) == 1:
                return format_usage(items[0], precedence)
            text = " | ".join(format_usage(x, 1) or "ε" for x in items) or "∅"
            return f"({text})" if precedence > 1 and len(items) > 1 else text
        case OptionalUsage(item):
            return f"[{format_usage(item)}]"
        case Repetition(item, separator):
            text = format_usage(item, 3)
            if separator is None:
                return f"[{text} ...]"
            return f"{text} [{shlex.quote(separator)} {text} ...]"
        case Unordered(items):
            return (
                "{"
                + "; ".join(format_usage(x) for x in items)
                + "} (optional, any order)"
            )


@dataclasses.dataclass
class Entry:
    """One help entry with resolved fields and a subordinate definition scope."""

    usage: Usage
    description: str | None
    examples: tuple[tuple[str, ...], ...]
    section: enum.Enum | None
    order: int
    scope: "Scope"
    name: str | None = None


@dataclasses.dataclass
class Scope:
    """Contain ordered entries, identity-keyed definitions, and grouping metadata."""

    entries: list[Entry] = dataclasses.field(default_factory=list)
    definitions: dict[int, Entry] = dataclasses.field(default_factory=dict)
    annotations: list[Annotation] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Document:
    """Resolved help model, reusable without reevaluating providers."""

    scope: Scope
    section_order: tuple[enum.Enum, ...] = ()

    def command_names(self) -> set[str]:
        """Return case-preserving literal heads of visible top-level entries.

        Every alternative must start with a literal, possibly wrapped in an
        annotation or nonempty sequence. Empty, optional, reference, repeated,
        unordered, and opaque leading syntax raises HelpError. This is not a
        nullable FIRST-set calculation and does not inspect subordinate entries.
        """
        return set().union(*(_command_heads(e.usage) for e in self.scope.entries))

    def for_command(self, topic: str) -> "Document":
        """Copy matching top-level entries and reachable definitions, without providers.

        Matching is exact and case-sensitive. An absent topic returns an empty
        document; a separate application-owned catalogue is needed to distinguish
        unknown topics from topics omitted by visibility or section filtering.
        The source model is not mutated, and mutable scopes/entries are copied.
        """
        entries = [e for e in self.scope.entries if topic in _command_heads(e.usage)]
        if not entries:
            return Document(Scope(), self.section_order)
        return Document(
            _Selection().scope(self.scope, entries=entries), self.section_order
        )

    def render(
        self,
        *,
        description_layout: Mode["inline", "below"] = "inline",
        definition_layout: Mode["entry", "section"] = "entry",
        repeat_section_headings: bool = True,
        example_formatter: Callable[[Sequence[str]], str] = shlex.join,
    ) -> str:
        """Render resolved scopes without providers, using opt-in presentation choices.

        Defaults keep descriptions inline and definitions local to each entry.
        Section sharing rejects ambiguous names or incompatible relative graphs
        with HelpError. The example formatter receives complete token sequences.
        """
        if description_layout not in ("inline", "below"):
            raise ValueError("description_layout must be 'inline' or 'below'")
        if definition_layout not in ("entry", "section"):
            raise ValueError("definition_layout must be 'entry' or 'section'")
        lines: list[str] = []

        def scope_lines(
            scope: Scope,
            indent: str,
            active: frozenset[int],
            inherited: enum.Enum | None = None,
        ) -> None:
            """Order presentation entries without altering executable alternatives."""
            for annotation in scope.annotations:
                if annotation.description:
                    lines.append(indent + annotation.description)
                for example in annotation.examples or ():
                    if example:
                        lines.append(indent + "  e.g. " + example_formatter(example))
            sections = list(dict.fromkeys(entry.section for entry in scope.entries))
            ordered: list[enum.Enum | None] = list(
                dict.fromkeys(x for x in self.section_order if x in sections)
            )
            for section in sections:
                if section is None:
                    if section not in ordered:
                        ordered.append(section)
                else:
                    ordered.extend(
                        x for x in type(section) if x in sections and x not in ordered
                    )
            for section in ordered:
                prefix = indent
                if section is not None and (
                    repeat_section_headings or section != inherited
                ):
                    lines.append(indent + str(section.value) + ":")
                    prefix += "  "
                entries = sorted(
                    (e for e in scope.entries if e.section == section),
                    key=lambda e: e.order,
                )
                definitions = (
                    _section_definitions(entries, active)
                    if definition_layout == "section"
                    else {}
                )
                for entry in entries:
                    entry_lines(
                        entry, prefix, active, expand=definition_layout == "entry"
                    )
                for identity, definition in definitions.items():
                    entry_lines(definition, prefix, active | {identity})

        def entry_lines(
            entry: Entry, indent: str, active: frozenset[int], *, expand: bool = True
        ) -> None:
            """Expand only definitions reachable from this retained entry."""
            label = f"<{entry.name}> = " if entry.name else ""
            text = label + format_usage(entry.usage)
            if entry.description and description_layout == "inline":
                text += f": {entry.description}"
            lines.append(indent + text)
            if entry.description and description_layout == "below":
                lines.append(indent + "  " + entry.description)
            for note in _notes(entry.usage):
                lines.append(indent + "  " + note)
            for example in entry.examples:
                if example:
                    lines.append(indent + "  e.g. " + example_formatter(example))
            scope_lines(entry.scope, indent + "  ", active, entry.section)
            seen: set[int] = set(active)
            for ref in _references(entry.usage) if expand else ():
                if ref.identity not in seen and ref.identity in entry.scope.definitions:
                    seen.add(ref.identity)
                    entry_lines(
                        entry.scope.definitions[ref.identity],
                        indent + "  ",
                        frozenset(seen),
                    )

        scope_lines(self.scope, "", frozenset())
        return "\n".join(lines)


def _command_heads(usage: Usage) -> set[str]:
    """Discover strict, nonnullable literal prefixes without resolving references."""
    match usage:
        case Literal(text):
            return {text}
        case Annotation(item):
            return _command_heads(item)
        case SequenceUsage(items) if items:
            return _command_heads(items[0])
        case Alternatives(items) if items:
            return set().union(*(_command_heads(item) for item in items))
        case _:
            raise HelpError(
                f"command discovery requires a nonoptional literal prefix; got {type(usage).__name__}"
            )


class _Selection:
    """Copy retained model graphs with identity memoization and reference pruning."""

    def __init__(self) -> None:
        """Keep copy ownership local to one selection, including recursive graphs."""
        self.scopes: dict[int, Scope] = {}
        self.entries: dict[int, Entry] = {}

    def entry(self, source: Entry) -> Entry:
        """Copy an entry before descending so named recursive references terminate."""
        identity = id(source)
        if identity not in self.entries:
            result = dataclasses.replace(source, scope=Scope())
            self.entries[identity] = result
            result.scope = self.scope(
                source.scope, references=_references(source.usage)
            )
        return self.entries[identity]

    def scope(
        self,
        source: Scope,
        *,
        entries: list[Entry] | None = None,
        references: Sequence[Reference] = (),
    ) -> Scope:
        """Copy entries and only the definition edges used by their owning usage."""
        identity = id(source)
        retained = source.entries if entries is None else entries
        if identity not in self.scopes:
            result = Scope(annotations=source.annotations.copy())
            self.scopes[identity] = result
            result.entries = [self.entry(entry) for entry in retained]
        result = self.scopes[identity]
        roots = list(references)
        roots.extend(ref for entry in retained for ref in _references(entry.usage))
        for ref in roots:
            if (
                ref.identity in source.definitions
                and ref.identity not in result.definitions
            ):
                # Entry memoization closes recursive definition edges.
                definition = source.definitions[ref.identity]
                result.definitions[ref.identity] = self.entry(definition)
        return result


def _same_definition(left: Entry, right: Entry, seen: set[tuple[int, int]]) -> bool:
    """Compare resolved relative definition graphs without following cycles twice."""
    key = (id(left), id(right))
    if key in seen:
        return True
    seen.add(key)
    if (
        left.usage != right.usage
        or left.description != right.description
        or left.examples != right.examples
        or left.section != right.section
        or left.order != right.order
        or left.name != right.name
        or left.scope.annotations != right.scope.annotations
        or len(left.scope.entries) != len(right.scope.entries)
        or left.scope.definitions.keys() != right.scope.definitions.keys()
    ):
        return False
    return all(
        _same_definition(a, b, seen)
        for a, b in zip(left.scope.entries, right.scope.entries)
    ) and all(
        _same_definition(value, right.scope.definitions[identity], seen)
        for identity, value in left.scope.definitions.items()
    )


def _section_definitions(
    entries: Sequence[Entry], active: frozenset[int]
) -> dict[int, Entry]:
    """Hoist direct references only when identity, names, and relative scopes agree."""
    result: dict[int, Entry] = {}
    names: dict[str, int] = {}
    for entry in entries:
        for ref in _references(entry.usage):
            if ref.identity in active or ref.identity not in entry.scope.definitions:
                continue
            definition = entry.scope.definitions[ref.identity]
            if ref.name in names and names[ref.name] != ref.identity:
                raise HelpError(
                    f"section definitions have conflicting name {ref.name!r}; use definition_layout='entry'"
                )
            if ref.identity in result and not _same_definition(
                result[ref.identity], definition, set()
            ):
                raise HelpError(
                    f"section definition {ref.name!r} has different relative scopes; use definition_layout='entry'"
                )
            names[ref.name] = ref.identity
            result.setdefault(ref.identity, definition)
    return result


def _references(usage: Usage) -> list[Reference]:
    """Collect reference occurrences in grammar order."""
    match usage:
        case Reference():
            return [usage]
        case SequenceUsage(items) | Alternatives(items) | Unordered(items):
            return [ref for item in items for ref in _references(item)]
        case OptionalUsage(item) | Repetition(item) | Annotation(item):
            return _references(item)
        case _:
            return []


def _notes(usage: Usage) -> list[str]:
    """Collect inline descriptions without losing their grammar location."""
    match usage:
        case Annotation(item, description):
            return (
                [f"{format_usage(item)}: {description}"] if description else []
            ) + _notes(item)
        case SequenceUsage(items) | Alternatives(items) | Unordered(items):
            return [note for item in items for note in _notes(item)]
        case OptionalUsage(item) | Repetition(item):
            return _notes(item)
        case _:
            return []


def _examples(
    usage: Usage, definitions: dict[int, Entry] | None = None
) -> tuple[tuple[str, ...], ...]:
    """Derive at most eight structural examples, never executing validation code."""
    match usage:
        case Annotation(item, _, examples):
            return examples if examples is not None else _examples(item, definitions)
        case Reference(_, identity):
            return (
                definitions[identity].examples
                if definitions and identity in definitions
                else ()
            )
        case Literal(text):
            return ((text,),)
        case Argument(_, example):
            return (example,) if example is not None else ()
        case SequenceUsage(items):
            values: tuple[tuple[str, ...], ...] = ((),)
            for item in items:
                values = tuple(
                    a + b
                    for a, b in itertools.islice(
                        itertools.product(values, _examples(item, definitions)), 8
                    )
                )
            return values
        case Alternatives(items):
            return tuple(
                itertools.islice(
                    (value for item in items for value in _examples(item, definitions)),
                    8,
                )
            )
        case OptionalUsage(item) | Repetition(item):
            return _examples(item, definitions)
        case Unordered(items):
            return _examples(SequenceUsage(items), definitions)
        case _:
            return ()


_LEAVES: dict[type[p.Parser[Any]], Argument] = {
    p.AnyStr: Argument("TEXT", ("text",)),
    p.Url: Argument("URL", ("https://example.org",)),
    p.Int: Argument("123", ("123",)),
    p.Float: Argument("1.23", ("1.23",)),
    p.HhMm: Argument("hh:mm", ("12:30",)),
    p.Interval: Argument("INTERVAL", ("1h30m",)),
    p.Date: Argument("DATE", ("tomorrow",)),
    p.Time: Argument("TIME", ("12:30",)),
    p.Meters: Argument("DISTANCE", ("1km",)),
}

_TRANSPARENT = (
    p.Map,
    p.Capture,
    p.CaptureOnly,
    p.Callback,
    p.Remaining,
    p.IfThen,
    p.Labeled,
    p.Weekday,
    p.DateTime,
    p.TimeOrDateTime,
)


class _Build:
    """Keep all traversal state and provider evaluation local to one request."""

    def __init__(
        self,
        owner: object,
        context: object,
        sections: Sequence[enum.Enum] | None,
        section_order: Sequence[enum.Enum] | None,
    ) -> None:
        """Initialize ownership, filters, provider cache, and recursion guards."""
        self.owner = owner
        self.context = context
        self.sections = sections
        self.section_order = tuple(section_order or ())
        self.values: dict[tuple[int, str], Any] = {}
        self.active: set[int] = set()
        self.defining: dict[int, Entry] = {}
        self.definition_depth = 0

    def value(self, meta: Meta[Any], field: str, path: str) -> Any:
        """Evaluate a field once per wrapper, attributing provider exceptions."""
        spec = meta._spec
        if spec.owner is not None and spec.owner is not self.owner:
            raise HelpError(f"{path}: contextual Meta belongs to another Help instance")
        key = (id(meta), field)
        if key not in self.values:
            value = getattr(spec, field)
            try:
                self.values[key] = value(self.context) if callable(value) else value
            except Exception as error:
                raise HelpError(f"{path}.{field}: {error}") from error
        return self.values[key]

    def document(self, parser: p.Parser[Any]) -> Document:
        """Create a root entry unless the grammar declares its own root entries."""
        scope = Scope()
        if self.sections is not None and not self.sections:
            return Document(scope, self.section_order)
        usage = self.walk(parser, scope, None, "root", root=True)
        root_section = parser._spec.section if isinstance(parser, Meta) else None
        if (
            not scope.entries
            and usage is not None
            and (self.sections is None or root_section in self.sections)
        ):
            scope.entries.append(
                Entry(
                    usage,
                    None,
                    _examples(usage, scope.definitions),
                    root_section,
                    0,
                    Scope(definitions=scope.definitions),
                )
            )
        return Document(scope, self.section_order)

    def walk(
        self,
        parser: p.Parser[Any],
        scope: Scope,
        section: enum.Enum | None,
        path: str,
        *,
        root: bool = False,
    ) -> Usage | None:
        """Traverse known grammar nodes; reject opaque implementations and bare cycles."""
        identity = id(parser)
        if identity in self.active:
            if isinstance(parser, Meta) and parser._spec.mode == "reference":
                return self.meta(parser, scope, section, path, root=root)
            raise HelpError(
                f"{path}: recursive grammar requires a named Meta reference"
            )
        self.active.add(identity)
        # Required branches publish their presentation contributions atomically.
        entry_count = len(scope.entries)
        definitions = scope.definitions.copy()
        try:
            if isinstance(parser, Meta):
                return self.meta(parser, scope, section, path, root=root)
            usage = self.node(parser, scope, section, path, root=root)
            if usage is None and isinstance(parser, (p.Adjacent, p.Seq)):
                del scope.entries[entry_count:]
                scope.definitions.clear()
                scope.definitions.update(definitions)
            return usage
        finally:
            self.active.remove(identity)

    def meta(
        self,
        meta: Meta[Any],
        scope: Scope,
        inherited: enum.Enum | None,
        path: str,
        *,
        root: bool = False,
    ) -> Usage | None:
        """Apply presentation boundaries and construct identity-based definitions."""
        spec = meta._spec
        section = spec.section if spec.section is not None else inherited
        path += "/" + (spec.name or spec.mode)
        visible = self.value(meta, "visible", path)
        if visible is False:
            return None
        if (
            spec.mode == "entry"
            and not self.definition_depth
            and self.sections is not None
            and section not in self.sections
        ):
            return None
        identity = id(meta)
        if spec.mode == "reference":
            if identity in scope.definitions:
                return Reference(cast(str, spec.name), identity)
            if identity in self.defining:
                scope.definitions[identity] = self.defining[identity]
                return Reference(cast(str, spec.name), identity)
        child = Scope() if spec.mode != "inline" else scope
        entry = Entry(
            SequenceUsage(),
            None,
            (),
            section,
            spec.order,
            child,
            spec.name if spec.mode == "reference" else None,
        )
        if spec.mode == "reference":
            scope.definitions[identity] = entry
        usage = self.value(meta, "usage", path)
        overridden = usage is not None
        grammar = self.value(meta, "grammar", path)
        parser = meta.parser
        if grammar is not None:
            if not isinstance(parser, p.Delayed):
                raise HelpError(
                    f"{path}.grammar: only Delayed accepts an explicit grammar provider"
                )
            parser = grammar
        if isinstance(parser, p.Conditional) and spec.visible is not None:
            parser = parser.parser
        if usage is not None:
            if self.known_composite(parser):
                raise HelpError(
                    f"{path}.usage: cannot replace executable composite syntax"
                )
            usage = Argument(usage) if isinstance(usage, str) else usage
        else:
            self.definition_depth += int(spec.mode == "reference")
            if spec.mode == "reference":
                self.defining[identity] = entry
            try:
                usage = self.walk(
                    parser, child, section, path, root=root and spec.mode == "inline"
                )
            finally:
                self.definition_depth -= int(spec.mode == "reference")
                if spec.mode == "reference":
                    self.defining.pop(identity, None)
        if usage is None:
            if spec.mode == "reference":
                scope.definitions.pop(identity, None)
            return None
        description = self.value(meta, "description", path)
        examples = self.value(meta, "examples", path)
        if examples is not None and (
            isinstance(examples, str)
            or any(
                isinstance(x, str) or any(not isinstance(token, str) for token in x)
                for x in examples
            )
        ):
            raise HelpError(f"{path}.examples: expected complete token sequences")
        defaults = (
            _examples(_LEAVES[type(parser)])
            if overridden and type(parser) in _LEAVES
            else _examples(usage, child.definitions)
        )
        entry.usage = usage
        entry.description = description
        entry.examples = (
            tuple(tuple(x) for x in examples) if examples is not None else defaults
        )
        if spec.mode == "entry":
            scope.entries.append(entry)
        elif spec.mode == "reference":
            return Reference(cast(str, spec.name), identity)
        elif description is not None or examples is not None or overridden:
            if root and scope.entries:
                # Root entries carry their own syntax; grouping metadata belongs
                # to their scope rather than a synthetic duplicate usage entry.
                scope.annotations.append(
                    Annotation(
                        usage,
                        description,
                        (
                            tuple(tuple(x) for x in examples)
                            if examples is not None
                            else None
                        ),
                    )
                )
            return Annotation(
                usage,
                description,
                tuple(tuple(x) for x in examples) if examples is not None else defaults,
            )
        return usage

    @staticmethod
    def known_composite(parser: p.Parser[Any]) -> bool:
        """Disallow overrides that hide known child grammar or conditional behavior."""
        from .commands import CommandsParser

        return isinstance(
            parser,
            (
                _TRANSPARENT
                + (
                    Meta,
                    p.Keyword,
                    p.Adjacent,
                    p.Then,
                    p.Seq,
                    p.OneOf,
                    p.Optional,
                    p.ValidOrMissing,
                    p.List,
                    p.Separated,
                    p.SomeOf,
                    p._SomeOfGeneral,
                    p.Conditional,
                    CommandsParser,
                )
            ),
        )

    def node(
        self,
        parser: p.Parser[Any],
        scope: Scope,
        section: enum.Enum | None,
        path: str,
        *,
        root: bool = False,
    ) -> Usage | None:
        """Extract supported parser structure without calling parsing callbacks."""
        from .commands import CommandsParser, Function

        def child(
            value: p.Parser[Any], label: str = "item", *, root: bool = False
        ) -> Usage | None:
            """Carry scope and a precise location into a child parser."""
            return self.walk(value, scope, section, path + "/" + label, root=root)

        if type(parser) in _LEAVES:
            return _LEAVES[type(parser)]
        if isinstance(parser, p.Empty):
            return SequenceUsage()
        if isinstance(parser, p.CaptureFixedStr):
            return Literal(parser.fixed_string)
        if isinstance(parser, (p.OneOfStrings, p.OneOfStringsIndex)):
            return Alternatives(tuple(Literal(x) for x in parser.strings))
        if isinstance(parser, p.OneOfEnumValue):
            return Alternatives(tuple(Literal(x.value) for x in parser.enum))
        if isinstance(parser, p.Bool):
            return Alternatives(
                tuple(Literal(x) for x in ("on", "true", "1", "off", "false", "0"))
            )
        if isinstance(parser, (p.RestAsStr, p.Concat)):
            item = Argument("TEXT", ("text",))
            return (
                Repetition(item)
                if isinstance(parser, p.Concat)
                else SequenceUsage((item, Repetition(item)))
            )
        if type(parser) in (p.PosIntSuffix, p.PosFloatSuffix):
            # These concrete built-ins own this structure; arbitrary regexes remain opaque.
            choices = cast(p.OneOf[Any], cast(p.GeneralSuffix[Any], parser).parser)
            external = cast(p.Map[Any, Any], choices.parsers[1]).parser
            pair = cast(p.Adjacent[Any, Any], external)
            suffixes = cast(p.OneOfStrings, pair.parser_right).strings
            number = "123" if type(parser) is p.PosIntSuffix else "1.23"
            return Alternatives(
                tuple(
                    form
                    for suffix in suffixes
                    for form in (
                        Argument(number + suffix, (number + suffix,)),
                        SequenceUsage((Argument(number, (number,)), Literal(suffix))),
                    )
                )
            )
        if isinstance(parser, _TRANSPARENT):
            return child(parser.parser, root=root)
        if isinstance(parser, p._SomeOfGeneral):
            return child(parser.parsers)
        if isinstance(parser, p.Keyword):
            value = child(parser.parser)
            return (
                SequenceUsage((Literal(parser.keyword), value))
                if value is not None
                else None
            )
        if isinstance(parser, (p.Adjacent, p.Then)):
            left, right = child(parser.parser_left, "left"), child(
                parser.parser_right, "right"
            )
            return (
                SequenceUsage((left, right))
                if left is not None and right is not None
                else None
            )
        if isinstance(parser, (p.Seq, p.OneOf, p.SomeOf)):
            values = [child(x, str(i)) for i, x in enumerate(parser.parsers)]
            items = tuple(x for x in values if x is not None)
            if values and not items:
                return SequenceUsage() if isinstance(parser, p.SomeOf) else None
            if isinstance(parser, p.Seq):
                return SequenceUsage(items) if len(items) == len(values) else None
            return (
                Unordered(items)
                if isinstance(parser, p.SomeOf)
                else Alternatives(items)
            )
        if isinstance(parser, (p.Optional, p.ValidOrMissing, p.List, p.Separated)):
            value = child(parser.parser)
            if value is None:
                return SequenceUsage() if not isinstance(parser, p.Separated) else None
            if isinstance(parser, (p.Optional, p.ValidOrMissing)):
                return OptionalUsage(value)
            return Repetition(
                value, parser.separator if isinstance(parser, p.Separated) else None
            )
        if isinstance(parser, CommandsParser):
            entries: list[Usage] = []
            nested = Scope()
            for command in parser.commands._commands:
                if not isinstance(command, Function):
                    raise HelpError(
                        f"{path}/{command.name}: custom Command requires a Function grammar"
                    )
                command_section = section
                command_order = 0
                if isinstance(command.parser, Meta):
                    command_section = command.parser._spec.section or section
                    command_order = command.parser._spec.order
                if (
                    self.sections is not None
                    and not self.definition_depth
                    and root
                    and command_section not in self.sections
                ):
                    continue
                command_scope = Scope()
                value = self.walk(
                    command.parser,
                    command_scope,
                    command_section,
                    path + "/" + command.name,
                )
                if value is None:
                    continue
                usage = SequenceUsage((Literal(command.name), value))
                entries.append(usage)
                nested.entries.append(
                    Entry(
                        usage,
                        command.description,
                        _examples(usage, command_scope.definitions),
                        command_section,
                        command_order,
                        command_scope,
                    )
                )
            if root:
                scope.entries.extend(nested.entries)
                return Alternatives(tuple(entries)) if entries else None
            identity = id(parser.commands)
            scope.definitions[identity] = Entry(
                Alternatives(tuple(entries)), None, (), None, 0, nested, "command"
            )
            return Reference("command", identity)
        raise HelpError(
            f"{path}: {type(parser).__name__} requires explicit Meta usage (Delayed: grammar provider; Conditional: visible predicate)"
        )
