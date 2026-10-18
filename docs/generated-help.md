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

1. Extract input-independent grammar builders from `homemau/commands.py`. `_Tail(text, ...)` currently captures original-input offsets; help must not fabricate an invocation to initialize such state. Keep input capture in the execution layer, or expose an opaque tail leaf with explicit repetition usage and a description of original-text preservation.
2. Annotate `_Word` with literal alternatives reflecting its case-sensitive behavior. Annotate `_LocalTime` with the structured one-/two-token alternatives above. Do not replace it with a superficially similar parser unless its actual accepted language and case rules match. Document calendar/DST validation as semantic constraints.
3. Fix grammar generation itself: `_recurrence_grammar` enumerates `ending="both"`, but `recurring` rejects simultaneous `until` and `for`. Construct mutually exclusive branches instead. Exclude outer `at` from calendar recurrence forms where the callback rejects it. Do not hide invalid branches only in metadata: parsing and help must share the corrected reusable grammar.
4. Extract reusable action subsets. Scheduled `status` is rejected semantically; exclude it structurally from the scheduled-action parser. Event templates accept restricted effects and reject status and other non-action commands; give event actions their own grammar and reference identity. Keep `until ack` notification-only restrictions explicit in the corresponding branch where practical.
5. Keep genuine semantic checks (calendar validity, future bounds, permissions, application-state checks) in execution and explain them in descriptions. Use complete examples that meet those constraints. Never claim arbitrary callbacks can be reverse-engineered into exact documentation.
6. Render the same parser graph used by execution. Replace the manually maintained syntax block only after tests compare representative accepted/rejected recurrence, scheduling, and event forms against generated syntax.

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
