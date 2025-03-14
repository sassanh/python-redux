# ruff: noqa: A003, D100, D101, D102, D103, D104, D105, D107
from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine, Sequence
from dataclasses import field
from types import NoneType
from typing import (
    TYPE_CHECKING,
    Any,
    Concatenate,
    Generic,
    Never,
    ParamSpec,
    Protocol,
    TypeAlias,
    TypeGuard,
    overload,
)

from immutable import Immutable
from typing_extensions import TypeVar

if TYPE_CHECKING:
    from asyncio import Task


T = TypeVar('T')

AwaitableOrNot = Awaitable[T] | T


class BaseAction(Immutable): ...


class BaseEvent(Immutable): ...


# Type variables
State = TypeVar('State', bound=Immutable | None, infer_variance=True)
Action = TypeVar('Action', bound=BaseAction | None, infer_variance=True)
Event = TypeVar('Event', bound=BaseEvent | None, infer_variance=True)
StrictEvent = TypeVar('StrictEvent', bound=BaseEvent, infer_variance=True)
SelectorOutput = TypeVar('SelectorOutput', infer_variance=True)
ComparatorOutput = TypeVar('ComparatorOutput', infer_variance=True)
ReturnType = TypeVar('ReturnType', infer_variance=True)
Comparator = Callable[[State], ComparatorOutput]
EventHandler = Callable[[Event], Any] | Callable[[], Any]
Args = ParamSpec('Args')
Payload = TypeVar('Payload', bound=Any, default=None)


class CompleteReducerResult(Immutable, Generic[State, Action, Event]):
    state: State
    actions: Sequence[Action] | None = None
    events: Sequence[Event] | None = None


ReducerResult = CompleteReducerResult[State, Action, Event] | State
ReducerType = Callable[[State | None, Action], ReducerResult[State, Action, Event]]


class InitializationActionError(Exception):
    def __init__(self: InitializationActionError, action: BaseAction) -> None:
        super().__init__(
            f"""The only accepted action type when state is None is "InitAction", \
action "{action}" is not allowed.""",
        )


class InitAction(BaseAction): ...


class FinishAction(BaseAction): ...


class FinishEvent(BaseEvent): ...


def is_complete_reducer_result(
    result: ReducerResult[State, Action, Event],
) -> TypeGuard[CompleteReducerResult[State, Action, Event]]:
    return isinstance(result, CompleteReducerResult)


def is_state_reducer_result(
    result: ReducerResult[State, Action, Event],
) -> TypeGuard[State]:
    return not isinstance(result, CompleteReducerResult)


class Scheduler(Protocol):
    def __call__(self: Scheduler, callback: Callable, *, interval: bool) -> None: ...


class TaskCreatorCallback(Protocol):
    def __call__(self: TaskCreatorCallback, task: Task) -> None: ...


class TaskCreator(Protocol):
    def __call__(
        self: TaskCreator,
        coro: Coroutine,
        *,
        callback: TaskCreatorCallback | None = None,
    ) -> None: ...


class ActionMiddleware(Protocol, Generic[Action]):
    def __call__(self: ActionMiddleware, action: Action) -> Action | None: ...


class EventMiddleware(Protocol, Generic[Event]):
    def __call__(self: EventMiddleware, event: Event) -> Event | None: ...


class CreateStoreOptions(Immutable, Generic[Action, Event]):
    auto_init: bool = False
    threads: int = 5
    scheduler: Scheduler | None = None
    action_middlewares: Sequence[ActionMiddleware[Action]] = field(default_factory=list)
    event_middlewares: Sequence[EventMiddleware[Event]] = field(default_factory=list)
    task_creator: TaskCreator | None = None
    on_finish: Callable[[], Any] | None = None
    grace_time_in_seconds: float = 1


# Autorun


class AutorunOptions(Immutable, Generic[ReturnType]):
    default_value: ReturnType | None = None
    auto_await: bool = True
    initial_call: bool = True
    reactive: bool = True
    memoization: bool = True
    keep_ref: bool = True
    subscribers_initial_run: bool = True
    subscribers_keep_ref: bool = True


AutorunOptionsWithDefault = AutorunOptions[ReturnType]
AutorunOptionsWithoutDefault = AutorunOptions[Never]


class AutorunReturnType(
    Protocol,
    Generic[ReturnType, Args],
):
    def __call__(
        self: AutorunReturnType,
        *args: Args.args,
        **kwargs: Args.kwargs,
    ) -> ReturnType: ...

    @property
    def value(self: AutorunReturnType) -> ReturnType: ...

    def subscribe(
        self: AutorunReturnType,
        callback: Callable[[ReturnType], Any],
        *,
        initial_run: bool | None = None,
        keep_ref: bool | None = None,
    ) -> Callable[[], None]: ...

    def unsubscribe(self: AutorunReturnType) -> None: ...

    __name__: str


class AutorunDecorator(Protocol, Generic[SelectorOutput, ReturnType]):
    @overload
    def __call__(
        self: AutorunDecorator,
        func: Callable[
            Concatenate[SelectorOutput, Args],
            ReturnType,
        ],
    ) -> AutorunReturnType[ReturnType, Args]: ...

    @overload
    def __call__(
        self: AutorunDecorator,
        func: Callable[
            Concatenate[SelectorOutput, Args],
            Awaitable[ReturnType],
        ],
    ) -> AutorunReturnType[Awaitable[ReturnType], Args]: ...


class UnknownAutorunDecorator(Protocol, Generic[SelectorOutput]):
    def __call__(
        self: UnknownAutorunDecorator,
        func: Callable[
            Concatenate[SelectorOutput, Args],
            ReturnType,
        ],
    ) -> AutorunReturnType[ReturnType, Args]: ...


# View


class ViewOptions(Immutable, Generic[ReturnType]):
    default_value: ReturnType | None = None
    memoization: bool = True
    keep_ref: bool = True
    subscribers_initial_run: bool = True
    subscribers_keep_ref: bool = True


ViewOptionsWithDefault = ViewOptions[ReturnType]
ViewOptionsWithoutDefault = ViewOptions[Never]


class ViewReturnType(
    Protocol,
    Generic[ReturnType, Args],
):
    def __call__(
        self: ViewReturnType,
        *args: Args.args,
        **kwargs: Args.kwargs,
    ) -> ReturnType: ...

    @property
    def value(self: ViewReturnType) -> ReturnType: ...

    def subscribe(
        self: ViewReturnType,
        callback: Callable[[ReturnType], Any],
        *,
        initial_run: bool | None = None,
        keep_ref: bool | None = None,
    ) -> Callable[[], None]: ...

    def unsubscribe(self: ViewReturnType) -> None: ...


class ViewDecorator(
    Protocol,
    Generic[SelectorOutput, ReturnType],
):
    @overload
    def __call__(
        self: ViewDecorator,
        func: Callable[
            Concatenate[SelectorOutput, Args],
            ReturnType,
        ],
    ) -> ViewReturnType[ReturnType, Args]: ...

    @overload
    def __call__(
        self: ViewDecorator,
        func: Callable[
            Concatenate[SelectorOutput, Args],
            Awaitable[ReturnType],
        ],
    ) -> ViewReturnType[Awaitable[ReturnType], Args]: ...


class UnknownViewDecorator(Protocol, Generic[SelectorOutput]):
    def __call__(
        self: UnknownViewDecorator,
        func: Callable[
            Concatenate[SelectorOutput, Args],
            ReturnType,
        ],
    ) -> ViewReturnType[ReturnType, Args]: ...


# With Store


class WithStateDecorator(
    Protocol,
    Generic[SelectorOutput],
):
    def __call__(
        self: WithStateDecorator,
        func: Callable[Concatenate[SelectorOutput, Args], ReturnType],
    ) -> Callable[Args, ReturnType]: ...


class EventSubscriber(Protocol):
    def __call__(
        self: EventSubscriber,
        event_type: type[Event],
        handler: EventHandler[Event],
        *,
        keep_ref: bool = True,
    ) -> Callable[[], None]: ...


DispatchParameters: TypeAlias = Action | list[Action]


class Dispatch(Protocol, Generic[State, Action, Event]):
    def __call__(
        self: Dispatch,
        *items: Action | Event | list[Action | Event],
        with_state: Callable[[State | None], Action | Event | list[Action | Event]]
        | None = None,
    ) -> None: ...


class BaseCombineReducerState(Immutable):
    _id: str


class CombineReducerAction(BaseAction):
    _id: str


class CombineReducerInitAction(CombineReducerAction, InitAction, Generic[Payload]):
    key: str
    payload: Payload | None = None


class CombineReducerRegisterAction(CombineReducerAction, Generic[Payload]):
    key: str
    reducer: ReducerType
    payload: Payload | None = None


class CombineReducerUnregisterAction(CombineReducerAction):
    key: str


SnapshotAtom = (
    int
    | float
    | str
    | bool
    | NoneType
    | dict[str, 'SnapshotAtom']
    | list['SnapshotAtom']
)


class SubscribeEventCleanup(Immutable, Generic[StrictEvent]):
    unsubscribe: Callable[[], None]
    handler: EventHandler[StrictEvent]

    def __call__(self: SubscribeEventCleanup) -> None:
        self.unsubscribe()
