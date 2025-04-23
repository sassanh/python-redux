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
    Literal,
    Never,
    Protocol,
    TypeGuard,
    TypeVar,
    cast,
    overload,
)

from immutable import Immutable

if TYPE_CHECKING:
    from asyncio import Task

    from redux.autorun import Autorun
    from redux.side_effect_runner import SideEffectRunner


type AwaitableOrNot[T] = Awaitable[T] | T


class BaseAction(Immutable): ...


class BaseEvent(Immutable): ...


class InitAction(BaseAction): ...


class FinishAction(BaseAction): ...


class FinishEvent(BaseEvent): ...


type Comparator[State, ComparatorOutput] = Callable[[State], ComparatorOutput]
type EventHandler[Event] = Callable[[Event], Any] | Callable[[], Any]


Action_co = TypeVar(
    'Action_co',
    bound=BaseAction | None,
    default=None,
    covariant=True,
)
Event_co = TypeVar(
    'Event_co',
    bound=BaseEvent | None,
    default=None,
    covariant=True,
)
State = TypeVar('State', bound=Immutable)


class CompleteReducerResult(Immutable, Generic[State, Action_co, Event_co]):
    state: State
    actions: Sequence[Action_co] | None = None
    events: Sequence[Event_co] | None = None


type ReducerResult[
    State: Immutable,
    Action: BaseAction | None = None,
    Event: BaseEvent | None = None,
] = CompleteReducerResult[State, Action, Event] | State
type ReducerType[
    State: Immutable,
    Action: BaseAction,
    ReturnAction: BaseAction | None,
    ReturnEvent: BaseEvent | None,
] = Callable[
    [State | None, Action],
    ReducerResult[State, ReturnAction, ReturnEvent],
]


class InitializationActionError(Exception):
    def __init__(self: InitializationActionError, action: BaseAction) -> None:
        super().__init__(
            f"""The only accepted action type when state is None is "InitAction", \
action "{action}" is not allowed.""",
        )


def is_complete_reducer_result[
    State: Immutable,
    Action: BaseAction | None,
    Event: BaseEvent | None,
](
    result: ReducerResult[State, Action, Event],
) -> TypeGuard[CompleteReducerResult[State, Action, Event]]:
    return isinstance(result, CompleteReducerResult)


def is_state_reducer_result[
    State: Immutable,
    Action: BaseAction | None,
    Event: BaseEvent | None,
](
    result: ReducerResult[State, Action, Event],
) -> TypeGuard[State]:
    return not isinstance(result, CompleteReducerResult)


class Scheduler(Protocol):
    def __call__(self: Scheduler, callback: Callable, *, interval: bool) -> None: ...


class TaskCreatorCallback(Protocol):
    def __call__(self: TaskCreatorCallback, task: Task) -> None: ...


class TaskCreator(Protocol):
    def __call__(self: TaskCreator, coro: Coroutine) -> None: ...


class ActionMiddleware[Action: BaseAction](Protocol):
    def __call__(
        self: ActionMiddleware,
        action: Action | InitAction | FinishAction,
    ) -> Action | InitAction | FinishAction | None: ...


class EventMiddleware[Event: BaseEvent | None](Protocol):
    def __call__(
        self: EventMiddleware,
        event: Event | FinishEvent,
    ) -> Event | FinishEvent | None: ...


def default_autorun() -> type[Autorun]:
    from redux.autorun import Autorun

    return Autorun


def default_side_effect_runner() -> type[SideEffectRunner]:
    from redux.side_effect_runner import SideEffectRunner

    return SideEffectRunner


class StoreOptions[Action: BaseAction, Event: BaseEvent](Immutable):
    auto_init: bool = False
    side_effect_threads: int = 1
    scheduler: Scheduler | None = None
    action_middlewares: Sequence[ActionMiddleware[Action]] = field(
        default_factory=list,
    )
    event_middlewares: Sequence[EventMiddleware[Event]] = field(
        default_factory=list,
    )
    task_creator: TaskCreator | None = None
    on_finish: Callable[[], Any] | None = None
    grace_time_in_seconds: float = 1
    autorun_class: type[Autorun] = field(default_factory=default_autorun)
    side_effect_runner_class: type[SideEffectRunner] = field(
        default_factory=default_side_effect_runner,
    )


# Autorun


class AutorunOptions[ReturnType, AutoAwait: bool](Immutable):
    default_value: ReturnType | None = None
    auto_await: AutoAwait = cast('AutoAwait', val=True)
    initial_call: bool = True
    reactive: bool = True
    memoization: bool = True
    keep_ref: bool = True
    subscribers_initial_run: bool = True
    subscribers_keep_ref: bool = True


class AutorunReturnType[**Args, ReturnType](Protocol):
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


class AutorunDecorator[SelectorOutput, _AutoAwait: bool](Protocol):
    @overload
    def __call__[**Args, ReturnType](
        self: AutorunDecorator[SelectorOutput, Literal[True]],
        func: Callable[Concatenate[SelectorOutput, Args], Awaitable[ReturnType]],
    ) -> AutorunReturnType[Args, None]: ...

    @overload
    def __call__[**Args, ReturnType](
        self: AutorunDecorator[SelectorOutput, bool],
        func: Callable[Concatenate[SelectorOutput, Args], ReturnType],
    ) -> AutorunReturnType[Args, ReturnType]: ...


# View


class ViewOptions[ReturnType](Immutable):
    default_value: ReturnType | None = None
    memoization: bool = True
    keep_ref: bool = True
    subscribers_initial_run: bool = True
    subscribers_keep_ref: bool = True


type ViewOptionsWithDefault[ReturnType] = ViewOptions[ReturnType]
type ViewOptionsWithoutDefault = ViewOptions[Never]


class ViewReturnType[**Args, ReturnType](Protocol):
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


class ViewDecorator[SelectorOutput, ReturnType](Protocol):
    @overload
    def __call__[**Args](
        self: ViewDecorator,
        func: Callable[
            Concatenate[SelectorOutput, Args],
            ReturnType,
        ],
    ) -> ViewReturnType[Args, ReturnType]: ...

    @overload
    def __call__[**Args](
        self: ViewDecorator,
        func: Callable[
            Concatenate[SelectorOutput, Args],
            Awaitable[ReturnType],
        ],
    ) -> ViewReturnType[Args, Awaitable[ReturnType]]: ...


class UnknownViewDecorator[SelectorOutput](Protocol):
    def __call__[**Args, ReturnType](
        self: UnknownViewDecorator,
        func: Callable[
            Concatenate[SelectorOutput, Args],
            ReturnType,
        ],
    ) -> ViewReturnType[Args, ReturnType]: ...


# With Store


class WithStateDecorator[SelectorOutput](Protocol):
    def __call__[**Args, ReturnType](
        self: WithStateDecorator,
        func: Callable[Concatenate[SelectorOutput, Args], ReturnType],
    ) -> Callable[Args, ReturnType]: ...


class EventSubscriber(Protocol):
    def __call__[Event](
        self: EventSubscriber,
        event_type: type[Event],
        handler: EventHandler[Event],
        *,
        keep_ref: bool = True,
    ) -> Callable[[], None]: ...


type DispatchParameters[Action: BaseAction] = Action | Sequence[Action]


class Dispatch[
    State: Immutable,
    Action: BaseAction,
    Event: BaseEvent | None,
](Protocol):
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


class CombineReducerInitAction[Payload](CombineReducerAction, InitAction):
    key: str
    payload: Payload | None = None


class CombineReducerRegisterAction[Payload](CombineReducerAction):
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


class SubscribeEventCleanup[Event: BaseEvent](Immutable):
    unsubscribe: Callable[[], None]
    handler: EventHandler[Event]

    def __call__(self: SubscribeEventCleanup) -> None:
        self.unsubscribe()
