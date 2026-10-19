"""Generic asynchronous command dispatch built on argparsec's token parsers."""

import logging
import re
from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine, Awaitable
from dataclasses import dataclass
from typing import Any, overload
from collections.abc import Sequence
from enum import Enum

from . import parser as p
from . import utils
from .help import Help, render_help

logger = logging.getLogger(__name__)

__all__ = [
    "Command",
    "CommandParseError",
    "Commands",
    "CommandsException",
    "CommandsParser",
    "Function",
    "Invocation",
    "InvocationEmptyError",
    "MarkedWord",
    "ParseError",
    "Prepared",
    "PreparedValue",
    "mark_words",
]


class CommandsException(Exception):
    """Base exception for command-processing failures."""


class ParseError(CommandsException):
    """Base exception for invalid command input."""


class InvocationEmptyError(ParseError):
    """Indicate that tokenization found no command name."""


@dataclass
class MarkedWord:
    """Associate an original token with its error-highlighting state."""

    word: str
    marked: bool


def mark_words(args: list[str], processed: int) -> list[MarkedWord]:
    """Mark a zero-based failure token; an end-of-input offset marks no token."""
    return [
        MarkedWord(word=word, marked=idx == processed) for idx, word in enumerate(args)
    ]


class CommandParseError(ParseError):
    """Carry the parser diagnostic alongside the original marked invocation."""

    marked_args: list[MarkedWord]

    def __init__(self, message: str, marked_args: list[MarkedWord]) -> None:
        """Retain the diagnostic and caller-supplied highlighting information."""
        super().__init__(message)
        self.marked_args = marked_args


@dataclass
class Invocation:
    """Represent a command name and its already-tokenized argument list."""

    name: str
    args: list[str]

    @staticmethod
    def parse(message: str) -> "Invocation":
        """Split literal spaces after stripping a # comment; reject empty input."""
        command = utils.assert_some(
            re.match(r"^[^#]*", message), "This should always match"
        )[0]
        fields = [field for field in re.split(r"  *", command) if field != ""]
        if len(fields):
            logger.debug("Command: %s", fields)
            return Invocation(name=fields[0], args=fields[1:])
        else:
            raise InvocationEmptyError()


class Command[Context](ABC):
    """Define an asynchronous handler with application-owned context."""

    name: str
    description: str

    def __init__(self, name: str, description: str) -> None:
        """Store the dispatch name and help description."""
        self.name = name
        self.description = description

    @abstractmethod
    async def invoke(self, context: Context, invocation: Invocation) -> None:
        """Execute the handler with the supplied context and invocation."""
        pass

    @abstractmethod
    def parse(self, context: Context, invocation: Invocation) -> bool:
        """Provide a command-specific boolean check without invoking its handler."""
        pass


@dataclass(frozen=True)
class Prepared[Context]:
    """Hold a validated deferred callback, reusable with caller-supplied contexts.

    Invocation does not parse again. Captured values are retained by reference,
    not copied, and callback exceptions propagate to the caller.
    """

    _callback: Callable[[Context], Awaitable[None]]

    async def invoke(self, context: Context) -> None:
        """Execute the captured callback; each awaited call executes it again."""
        await self._callback(context)


@dataclass(frozen=True)
class PreparedValue[Context, Value]:
    """Expose a validated value and its captured deferred handler.

    The value binding is read-only, but the object is retained by reference, not
    copied or deeply immutable. Mutating it can affect later invocations. This
    is not a capability or security boundary. Handler exceptions propagate.
    """

    value: Value
    _callback: Callable[[Context, Value], Awaitable[None]]

    async def invoke(self, context: Context) -> None:
        """Pass the retained object to the handler on every call, without parsing."""
        await self._callback(context, self.value)


class Function[Context, Parsed](Command[Context]):
    """Validate arguments and pass the parsed value to an asynchronous callback."""

    parser: p.Parser[Parsed]
    fn: list[Callable[[Context, Parsed], Coroutine[Any, Any, None]]]

    def __init__(
        self,
        name: str,
        description: str,
        parser: p.Parser[Parsed],
        fn: Callable[[Context, Parsed], Coroutine[Any, Any, None]],
    ) -> None:
        """Bind parser and callback without executing either."""
        super().__init__(name, description)
        self.parser = parser
        self.fn = [fn]

    async def invoke(self, context: Context, invocation: Invocation) -> None:
        """Parse arguments before execution, raising a marked diagnostic on failure."""
        await self.prepare(invocation).invoke(context)

    def prepared_parser(self) -> p.Parser[Prepared[Context]]:
        """Parse arguments into deferred execution, exposing the argument help grammar.

        This does not consume or check the Function name. Consumption and failures
        match the argument parser; use Remaining per alternative for complete
        validation before OneOf selection. Parsing runs validators but never the
        execution callback. The selected callback and value are captured on success.
        """

        def opaque(value: PreparedValue[Context, Parsed]) -> Prepared[Context]:
            """Expose only deferred execution of the shared typed preparation."""
            return Prepared(value.invoke)

        return p.Map(opaque, self.prepared_value_parser())

    def prepared_value_parser(self) -> p.Parser[PreparedValue[Context, Parsed]]:
        """Parse arguments once into a typed value and deferred execution.

        Consumption, failures, and argument-only help match prepared_parser().
        Parsing runs validators, never the handler. The current handler and exact
        parsed object are captured on success; invocation never reparses. The
        parser view retains the argument grammar present when it is created.
        """

        def bind(value: Parsed) -> PreparedValue[Context, Parsed]:
            """Capture the current handler and value without copying or execution."""
            return PreparedValue(value, self.fn[0])

        return p.Map(bind, self.parser)

    def prepare(self, invocation: Invocation) -> Prepared[Context]:
        """Validate arguments once or raise the same marked error as invoke.

        The invocation name is diagnostic only, matching direct Function.invoke.
        Prefix acceptance follows the argument parser's contract.
        """
        validated = self.prepared_parser().parse(invocation.args)
        if isinstance(validated, p.ParseFail):
            marked_args = [MarkedWord(word=invocation.name, marked=False)]
            marked_args.extend(mark_words(invocation.args, validated.processed))
            raise CommandParseError(validated.message, marked_args=marked_args)
        assert isinstance(validated, p.ParseOK)
        return validated.value

    def parse(self, context: Context, invocation: Invocation) -> bool:
        """Preserve the legacy non-None check; this does not reject ParseFail."""
        return self.parser(invocation.args) is not None


class CommandsParser[Context](p.Parser[Callable[[Context], Awaitable[None]]]):
    """Recognize registered command names and produce deferred invocation callbacks."""

    commands: "Commands[Context]"

    def __init__(self, commands: "Commands[Context]") -> None:
        """Keep a live reference to the registry, including later registrations."""
        self.commands = commands

    def parse(
        self, args: list[str]
    ) -> p.ParseResult[Callable[[Context], Awaitable[None]]]:
        """Consume a known command; argument validation happens only during execution."""
        if len(args) == 0:
            return p.ParseFail("No command name", processed=0)
        invocation = Invocation(args[0], args[1:])
        if self.commands.has_command(invocation.name):

            async def invoke(context: Context) -> None:
                """Validate and execute against the registry when explicitly awaited."""
                await self.commands.invoke(context, invocation)

            return p.ParseOK(invoke, processed=len(args))
        else:
            return p.ParseFail(f"No such command: {invocation.name}", processed=0)


class Commands[Context]:
    """Register commands and dispatch matching names sequentially without owning context."""

    _commands: list[Command[Context]]

    def __init__(self) -> None:
        """Create an empty registry with registration-order dispatch."""
        self._commands = []

    def register(self, command: Command[Context]) -> None:
        """Append a handler; duplicate names remain allowed."""
        self._commands.append(command)

    def has_command(self, name: str) -> bool:
        """Check registered names case-insensitively."""
        return bool(
            [
                command
                for command in self._commands
                if command.name.lower() == name.lower()
            ]
        )

    def parse(self, context: Context, invocation: Invocation) -> bool:
        """Check exact-name membership after asserting case-insensitive membership."""
        assert self.has_command(invocation.name)
        return bool(
            [command for command in self._commands if command.name == invocation.name]
        )

    async def invoke(self, context: Context, invocation: Invocation) -> None:
        """Await every case-insensitive match in order; an unknown name does nothing."""
        for command in self._commands:
            if command.name.lower() == invocation.name.lower():
                await command.invoke(context, invocation)

    @overload
    def help(
        self,
        *,
        sections: Sequence[Enum] | None = None,
        section_order: Sequence[Enum] | None = None,
    ) -> str:
        """Render context-free command grammar."""
        ...

    @overload
    def help[H](
        self,
        context: H,
        *,
        renderer: Help[H],
        sections: Sequence[Enum] | None = None,
        section_order: Sequence[Enum] | None = None,
    ) -> str:
        """Render with a typed help context independent of dispatch context."""
        ...

    def help(
        self,
        context: Any = None,
        *,
        renderer: Help[Any] | None = None,
        sections: Sequence[Enum] | None = None,
        section_order: Sequence[Enum] | None = None,
    ) -> str:
        """Generate live command syntax and descriptions without invoking handlers."""
        if renderer is None:
            return render_help(
                self.parser(), sections=sections, section_order=section_order
            )
        return renderer.render(
            self.parser(), context, sections=sections, section_order=section_order
        )

    def parser(self) -> CommandsParser[Context]:
        """Expose the registry as a deferred-execution token parser."""
        return CommandsParser(self)


logger.setLevel(logging.DEBUG)
