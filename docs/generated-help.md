# Generated help and migration guide

## API and guarantees

```python
import argparsec as p
import argparsec.help as h
import argparsec.commands as c
```

`p.Meta(parser, ...)` delegates parsing unchanged. Its independent optional fields are `usage`, `examples`, and `description`. `None` means derive/default; `examples=[]` explicitly suppresses examples. Examples are collections of complete token tuples, such as `[("at", "12:30", "info")]`, not strings to split. The renderer quotes tokens for display; it does not prescribe a tokenizer. Defaults include `Int` → `123`, `HhMm` → `hh:mm` with example `12:30`. A leaf usage label does not discard its built-in examples.

`p.render_help(parser, sections=None, section_order=None)` renders context-free metadata. `h.Help[C].document(parser, context, ...)` returns a resolved `Document` containing `Scope`, `Entry`, and structured usage objects. `Document.render()` does not reevaluate providers. `Help.render(...)` combines these operations. Each render request has fresh state.

The usage model contains `Literal`, `Argument`, `SequenceUsage`, `Alternatives`, `OptionalUsage`, `Repetition`, `Reference`, `Unordered`, and inline `Annotation`. `SequenceUsage(())` consumes no syntax; `Alternatives(())` represents no choices. `h.format_usage` preserves alternative precedence and groups multi-token repeated items. `List(item)` displays `[ITEM ...]`; `Separated(item, "and")` displays `ITEM [and ITEM ...]`. `SomeOf` displays optional, unordered, at-most-once components. Alternative order remains declaration order, irrespective of presentation sorting.

Known wrappers (`Map`, `Capture`, `CaptureOnly`, `Remaining`, `Callback`, `Labeled`, `IfThen`, and their derived helpers) expose their child grammar. `Empty` contributes no syntax. Mapping callbacks, validators, conditions, parsing methods, and command handlers are not executed. Known wrapper subclasses must retain their inherited structural contract; a custom implementation with a different grammar needs an explicit opaque parser boundary.

Help describes structural syntax, not proof of acceptance for arbitrary Python predicates, semantic validators, speculative combinator behavior, or mutable external state. Derived examples are bounded to eight structural combinations and are not validated by executing callbacks. Supply semantic-safe examples, or an empty collection, where validation depends on state or time.

## Presentation and scopes

`Meta` accepts `mode`, `name`, `section`, and `order`:

- `mode="inline"` (default): preserve syntax within the enclosing entry. Inline descriptions appear as located notes and examples participate in enclosing example composition.
- `mode="entry"`: declare a separate entry in the current scope. The renderer uses declared entries instead of synthesizing a root usage entry. Entry descendants have a subordinate scope.
- `mode="reference", name="action"`: emit `<action>` and a subordinate definition. This is also the named-grammar mechanism; there is no second definition wrapper.

The root is a help-entry scope. References and nested registries create relative subordinate scopes; there are no numeric nesting depths. Shared `Meta` identities share definitions within a scope. Distinct wrappers are distinct definitions even if their display names match. Give restricted variants distinctive names for readable output, such as `action-without-every`; names are not identity keys. Named recursive references terminate; unnamed recursive structures raise a located `HelpError`.

Sections can be members of any application-defined `Enum`. Default section order is enum declaration order (enum classes appear in first-encounter order). Within a section, entries retain grammar declaration order. `order` is a numeric presentation key with stable ties. `section_order=[...]` puts specified sections first, followed by remaining declared sections. `sections=[...]` retains only matching entries; `sections=[]` retains none. Unsectioned entries are included when there is no filter. Empty sections are omitted. Only definitions referenced by retained entries render; definitions themselves are not removed by section filters.

An inline grouping `Meta(..., section=...)` supplies an inherited section. A more specific entry section overrides it. A command's outermost `Meta` supplies its section and order; use inline mode there because the registry already creates the command entry. Registry descriptions come from `Function.description`, while parser metadata adds argument-level notes.

```python
import enum
import argparsec as p


class Section(enum.Enum):
    """Define public help ordering independently of parsing order."""

    BASIC = "Basic"
    SCHEDULING = "Scheduling"


action = p.Meta(
    p.OneOfStrings(["start", "stop"]),
    mode="reference",
    name="action",
)
grammar = p.OneOf(
    p.Meta(p.Keyword("run", action), mode="entry", section=Section.BASIC),
    p.Meta(
        p.Keyword("sequence", p.Separated(action, "and")),
        mode="entry",
        section=Section.SCHEDULING,
    ),
)
print(p.render_help(grammar, sections=[Section.SCHEDULING]))
```

## Command discovery and focused help

Resolve the grammar with `document = renderer.document(grammar, context, ...)`, applying visibility and section filters for the requesting user. `document.command_names()` returns a fresh `set[str]` of literal command heads from top-level entries only. `document.for_command(topic)` returns a separate resolved `Document` containing every matching top-level entry. Synonyms select the entire entry, not a rewritten usage fragment. Multiple entries and sections can match one head. Definitions and subordinate entries are not a separate command catalogue.

Discovery accepts `Literal`, `Annotation` around a supported prefix, nonempty `SequenceUsage` whose first component is supported, and nonempty `Alternatives` whose every branch is supported. It reads only the first sequence component: `cancel sub ID` contributes `cancel`, and `every INTERVAL until TIME` contributes `every`. A leading `Argument`, `Reference`, `OptionalUsage`, `Repetition`, `Unordered`, empty sequence, or empty alternative raises `HelpError`, including inside any prefix alternative. Leading references are not expanded, empty prefixes are not skipped, and nullable FIRST sets are not calculated. Tail syntax after a supported head is unrestricted. This is structural discovery, not an execution-based recognizer.

Matching preserves literal spelling and is exact and case-sensitive, including for documents built from case-insensitive command registries. Topic paths are single literal tokens, not multiword navigation. Applications implementing different matching policies must do so explicitly.

Selection retains section/order metadata, descriptions, examples (including suppression), inline annotations, general root/scope notes, subordinate entries, and definitions reachable from retained entry usages. General scope notes/examples apply to the scope and are retained unchanged when entries remain; attach command-specific notes/examples to entries. Unreachable definition edges are pruned. Mutable entries, scopes, and their collections are copied with graph memoization, preserving reference identity, relative ownership, same-name distinctions, and named cycles. Immutable usage nodes and example tuples can be shared. The source document is not modified. Discovery, selection, and rendering do not invoke parsers, semantic maps, validators, handlers, parsing factories, or resolved metadata providers. Rendering can invoke the explicitly supplied example formatter.

An absent topic returns an empty document without root notes. A filtered document intentionally cannot distinguish unknown commands from known commands with no visible entries. If that distinction is needed, applications must maintain or supply a separate trusted catalogue and choose their own error policy. Never expose hidden descriptions/examples by discovering topics from an unfiltered secret-bearing grammar. A separate static builtin-name catalogue for alias protection is not automatically a safe public help catalogue. There is no global discovery cache: resolving a fresh document uses the supplied context and current live registry; selecting an existing document uses that snapshot.

## Render configuration

`Document.render(...)`, `Help.render(...)`, and `render_help(...)` accept these keyword-only presentation options:

- `description_layout="inline"` (default) appends entry descriptions to usage; `"below"` places them on separate lines, indented two spaces from usage. Inline annotations remain located syntax/prose notes in both modes.
- `definition_layout="entry"` (default) expands reachable definitions beneath each referring entry. `"section"` places direct referenced definitions after all entries in each enclosing section, once per identity in that section. Unsectioned entries form their own group. Definitions use the section's entry indentation and first-reference order in presentation-sorted entries. Relative child scopes remain nested; this is not global graph flattening.
- `repeat_section_headings=True` (default) renders child section headings. `False` suppresses a child heading equal to its enclosing entry's section, without suppressing distinct headings.
- `example_formatter=shlex.join` (default) formats complete example token sequences. For whitespace-tokenizing consumers, `example_formatter=" ".join` is an explicit alternative. The hook applies to entry examples and root/scope examples; it does not change usage quoting or parsing.

Section-level sharing preserves identity, not just display names. Same-identity definitions must have equal resolved relative graphs (including metadata and child scopes); distinct direct identities must have distinct display names within the section. Conflicts raise `HelpError` advising `definition_layout="entry"`; the renderer does not silently merge or rename incompatible definitions. Named recursion terminates in either mode. Sharing does not cross sections or relative child-scope boundaries. Defaults preserve ordinary rendering behavior.

```python
text = document.for_command("run").render(
    description_layout="below",
    definition_layout="section",
    repeat_section_headings=False,
    example_formatter=" ".join,
)
```

Custom transports can consume `Document`, `Scope`, `Entry`, and structured usage directly to distinguish syntax from prose. Text indentation is presentation, not a transport format. HTML escaping, markup, bot prefixes, permissions, and application-specific alias context belong at the application boundary.

## Context typing and lazy providers

Keep dispatch context and help context independent. The context type is unbounded: it need not inherit a library base class.

```python
import dataclasses
import argparsec as p


@dataclasses.dataclass
class HelpContext:
    """Hold a synchronous snapshot for one help request."""

    vehicle_names: tuple[str, ...]
    admin: bool


help_renderer = p.Help[HelpContext]()
vehicle = help_renderer.meta(
    p.Delayed(lambda: p.OneOfStrings(["cached-at-parse-time"])),
    usage="VEHICLE",
    examples=lambda ctx: [(name,) for name in ctx.vehicle_names],
    description=lambda ctx: f"Choose one of {len(ctx.vehicle_names)} cached vehicles",
)
grammar = p.Keyword("wake", vehicle)
text = help_renderer.render(grammar, HelpContext(("Roadster",), False))
```

`Help[C].meta` accepts synchronous `C -> value` providers for usage, descriptions, and the entire example collection, plus `visible: C -> bool` and `grammar: C -> Parser[Any]`. Each field is evaluated at most once per `Meta` identity per render, even when shared across scopes. Hidden or filtered entries need not evaluate their other fields. Provider failures become `HelpError` with a grammar path and field name, retaining the original exception as the cause. Providers must return values, not awaitables; fetch asynchronous data before rendering.

`Meta[T]` retains the existing `Parser[T]` generic API. Contextful wrappers belong to their creating `Help[C]` instance. Mypy checks provider arguments and `render` contexts; passing a broader provider accepting a base context is safe. Rendering a contextful wrapper through another renderer raises `HelpError` before invoking its provider. This explicit ownership boundary prevents context erasure through existing combinators from becoming an unchecked cast. It also avoids adding a second context parameter to every parser and consuming application annotation. Context-free `Meta` and built-in parsers can be shared across all renderers. Applications combining contextful components should inject one shared renderer into their grammar builders.

`commands.help(context, renderer=help_renderer)` uses this typed rendering context independently of `Commands[DispatchContext]`. `commands.help()` handles context-free grammars. `commands.parser()` remains a live registry view: help sees registrations made after the parser was created. Custom `Command` subclasses need an executable argument grammar exposed through `Function` for automatic documentation; their arbitrary `invoke` implementations are not inspected. Duplicate command names preserve registry behavior and appear as distinct entries.

## Opaque and dynamic grammar boundaries

For a custom leaf, use `Meta(custom_parser, usage=h.Argument("VALUE"), ...)`. Multi-token opaque syntax needs structure, for example:

```python
local_time_usage = h.Alternatives((
    h.Argument("hh:mm", ("12:30",)),
    h.SequenceUsage((h.Argument("DATE", ("tomorrow",)), h.Argument("hh:mm", ("12:30",)))),
))
```

A string usage is an opaque argument label, not a parsed mini-language; use structured objects for literal tokens, alternatives, and sequences. A usage override cannot replace a known executable composite, including `Map`, `Keyword`, or a registry. Annotate the opaque leaf inside the composite instead. `Regex` is opaque: the library does not guess a human grammar from arbitrary regexes.

`Delayed` never calls its parsing factory for help implicitly. Either give it an opaque argument usage, or explicitly opt into a synchronous grammar provider:

```python
vehicle = help_renderer.meta(
    p.Delayed(lambda: p.OneOfStrings(["cached-at-parse-time"])),
    grammar=lambda ctx: p.OneOfStrings(list(ctx.vehicle_names)),
)
```

The provider is a separate help-time contract and must describe the same syntax for the supplied state snapshot. To deliberately reuse a parsing factory, pass `grammar=lambda ctx: factory()` explicitly; ensure it is safe to call. Only `Delayed` accepts this provider.

`Conditional` requires an immediate enclosing `help_renderer.meta(conditional, visible=...)`. Its parsing condition is not invoked. The visibility predicate selects whether that grammar exists in this help context; required sequences containing a hidden component disappear, while optional components can be omitted. A bare `Conditional` raises `HelpError`. Visibility is presentation, not authorization enforcement. For conditions that merely capture a construction-time Boolean, construct the actual enabled/disabled grammar instead.

## Agent migration: HomeMau

1. Resolve the executable grammar through the owning `Help` instance using the request's visibility context. Keep kitchen permissions, room configuration, and separately permission-filtered switch aliases in HomeMau. Do not manufacture runtime settings or invoke parsing to discover names; use input-independent structural grammar and explicitly supplied help providers.
2. Replace local `_leading_words()` traversal with `document.command_names()`. Use a separate trusted static document/catalogue for builtin/alias collision protection if needed; user-visible help topics must come from the permission-filtered document. Literal heads such as `every` are commands; internal modifiers such as `until` and `for` are not separately reserved.
3. Replace direct assignment to `document.scope.entries` with `document.for_command(topic)`. It retains all entries for heads such as `cancel` across sections, preserves synonym entries such as `notify`/`ping`, and keeps referenced action definitions for `at`. Topic errors and unknown-versus-hidden policy remain in the application. Focused topics do not expand saved aliases.
4. Replace recursive section-clearing and fragment rendering with `description_layout="below"`, `definition_layout="section"`, `repeat_section_headings=False`, and `example_formatter=" ".join` where these match the transport's presentation. Verify relative-scope compatibility; a hoisting conflict requires distinct definition names or entry-local rendering, not name-based merging. Matrix bold headings, syntax/prose markup, escaping, and prefix formatting remain application concerns; use the structured model when text indentation alone is insufficient.
5. Preserve the grammar's restricted scheduled/event-action references and its semantic checks for dates, DST, recurrence bounds, aliases, and permissions. Discovery and help selection must not alter parser acceptance, backtracking, callback counts, alias expansion depth, or effects. `CaptureOnly` executes its child's parsing/mapping callbacks and is not a callback-free structural recognizer.
6. Verify complete examples, focused synonyms, multi-entry heads, hidden sections, recursive/shared definitions, no semantic execution, and identical accepted/rejected commands. Keep prefixless conversational admission, alias expansion/cycle limits, and command dispatch policy in HomeMau. The README example and independent argparsec tests demonstrate the library APIs without making HomeMau a test dependency.

## Agent migration: TeslaBot

1. Preserve wrappers and `Empty`: `Map`, captures, `Remaining`, and labeled adjacency are transparent, while argument-free commands contribute only their registry name.
2. `ValidVehicle` is a mapping wrapper around a `Delayed(self.make_validator)` reading `cached_vehicle_list`. Put metadata on that delayed leaf. Use `usage="VEHICLE"` plus lazy cached examples, or an explicit grammar provider returning the current `OneOfStrings` choices. Do not trigger network refresh or async operations during rendering.
3. In `appscheduler.py`, keep `valid_schedulable` as an allowlist separate from the full command registry. Give each `include_every`/`include_until` variant its own named `Meta` identity, preferably with a distinct name. Reusing a broad `action` reference for a restricted nesting position would advertise commands the parser rejects.
4. Replace construction-time `Conditional(lambda: include_until, ...)` and the analogous `include_every` with actual grammar construction. For example, include an optional `until` keyword parser only when enabled, using `Empty` or an appropriate mapped zero-token value for the disabled branch while preserving the parsed result type. This avoids documenting inaccessible branches or evaluating parsing conditions for help.
5. Keep `Separated(allowlisted_action, "and")` as the source of sequence help. Preserve the `at` command's two executable alternatives, with and without the `sequence` keyword; do not rewrite its syntax merely to make a shorter help string.
6. Keep nested `set` commands as a nested `Commands` registry. Its live parser gives relative subordinate help scopes and sees later registrations. Add argument-level `Meta` sections/notes rather than duplicating registry names in hand-written usage strings.
7. Validate with self-contained tests: allowlist rejection, nested scheduler restrictions, separator-containing actions, optional keywords, argument-free commands, changing vehicle snapshots, and live nested registration. Sibling applications need not become test dependencies of argparsec.

## Verification checklist for migrations

- Run parser acceptance/rejection tests as well as help snapshot/model tests. Presentation visibility does not enforce permissions.
- Check grouping around alternatives and multi-token repetition; preserve declaration order for ambiguous grammars.
- Exercise shared references, same-name restricted variants, cycles, filtered sections, and nested scopes.
- Assert no execution callbacks run while rendering. Test provider failures and one-evaluation-per-request behavior.
- Type-check application and tests with the concrete help context, including a negative wrong-context/provider fixture.
