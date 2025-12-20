# ruff: noqa: D100, D101, D102, D103, D107
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
    ParamSpec,
    Protocol,
    TypeAlias,
    TypeGuard,
    cast,
    overload,
)

from immutable import Immutable
from typing_extensions import TypeVar

if TYPE_CHECKING:
    from asyncio import Task

    from redux.autorun import Autorun
    from redux.side_effect_runner import SideEffectRunner

T = TypeVar('T')

AwaitableOrNot = Awaitable[T] | T


class BaseAction(Immutable): ...


class BaseEvent(Immutable): ...


class InitAction(BaseAction): ...


class FinishAction(BaseAction): ...


class FinishEvent(BaseEvent): ...


# Type variables
State = TypeVar('State', bound=Immutable | None, infer_variance=True)
Action = TypeVar('Action', bound=BaseAction | None, infer_variance=True)
Event = TypeVar('Event', bound=BaseEvent | None, infer_variance=True)
StrictEvent = TypeVar('StrictEvent', bound=BaseEvent, infer_variance=True)
SelectorOutput = TypeVar('SelectorOutput', infer_variance=True)
ComparatorOutput = TypeVar('ComparatorOutput', infer_variance=True)
ReturnType = TypeVar('ReturnType', infer_variance=True)
Comparator = Callable[[State], ComparatorOutput]
EventHandler: TypeAlias = Callable[[Event], Any] | Callable[[], Any]
Args = ParamSpec('Args')
Payload = TypeVar('Payload', bound=Any, default=None)
MethodSelf = TypeVar('MethodSelf', bound=object, infer_variance=True)


class CompleteReducerResult(Immutable, Generic[State, Action, Event]):
    state: State
    actions: Sequence[Action] | None = None
    events: Sequence[Event] | None = None


ReducerResult: TypeAlias = CompleteReducerResult[State, Action, Event] | State
ReducerType: TypeAlias = Callable[
    [State | None, Action],
    ReducerResult[State, Action, Event],
]


class InitializationActionError(Exception):
    def __init__(self: InitializationActionError, action: BaseAction) -> None:
        super().__init__(
            f"""The only accepted action type when state is None is "InitAction", \
action "{action}" is not allowed.""",
        )


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
    ) -> None: ...


class ActionMiddleware(Protocol, Generic[Action]):
    def __call__(self: ActionMiddleware, action: Action) -> Action | None: ...


class EventMiddleware(Protocol, Generic[Event]):
    def __call__(self: EventMiddleware, event: Event) -> Event | None: ...


class StoreOptions(Immutable, Generic[Action, Event]):
    auto_init: bool = False
    side_effect_threads: int = 1
    scheduler: Scheduler | None = None
    action_middlewares: Sequence[ActionMiddleware[Action | InitAction]] = field(
        default_factory=list,
    )
    event_middlewares: Sequence[EventMiddleware[Event | FinishEvent]] = field(
        default_factory=list,
    )
    task_creator: TaskCreator | None = None
    on_finish: Callable[[], Any] | None = None
    grace_time_in_seconds: float = 1
    autorun_class: type[Autorun] = field(
        default_factory=lambda: __import__(
            'redux.autorun',
            fromlist=['redux'],
        ).Autorun,
    )
    side_effect_runner_class: type[SideEffectRunner] = field(
        default_factory=lambda: __import__(
            'redux.side_effect_runner',
            fromlist=['redux'],
        ).SideEffectRunner,
    )


# Autorun

AutoAwait = TypeVar(
    'AutoAwait',
    bound=(Literal[True, False] | None),
    infer_variance=True,
)

NOT_SET = object()


class AutorunOptionsType(Immutable, Generic[ReturnType, AutoAwait]):
    default_value: ReturnType | None = None
    auto_await: AutoAwait = cast('AutoAwait', val=None)
    initial_call: bool = True
    reactive: bool = True
    memoization: bool = True
    keep_ref: bool = True
    subscribers_initial_run: bool = True
    subscribers_keep_ref: bool = True

    @overload
    def __init__(
        self: AutorunOptionsType[ReturnType, None],  # type: ignore[reportInvalidTypeVar]
        *,
        default_value: ReturnType | None = None,
        auto_await: None = None,
        initial_call: bool = True,
        reactive: bool = True,
        memoization: bool = True,
        keep_ref: bool = True,
        subscribers_initial_run: bool = True,
        subscribers_keep_ref: bool = True,
    ) -> None: ...
    @overload
    def __init__(
        self: AutorunOptionsType[ReturnType, Literal[True]],  # type: ignore[reportInvalidTypeVar]
        *,
        default_value: ReturnType | None = None,
        auto_await: Literal[True],
        initial_call: bool = True,
        reactive: bool = True,
        memoization: bool = True,
        keep_ref: bool = True,
        subscribers_initial_run: bool = True,
        subscribers_keep_ref: bool = True,
    ) -> None: ...
    @overload
    def __init__(
        self: AutorunOptionsType[ReturnType, Literal[False]],  # type: ignore[reportInvalidTypeVar]
        *,
        default_value: ReturnType | None = None,
        auto_await: Literal[False],
        initial_call: bool = True,
        reactive: bool = True,
        memoization: bool = True,
        keep_ref: bool = True,
        subscribers_initial_run: bool = True,
        subscribers_keep_ref: bool = True,
    ) -> None: ...
    def __init__(  # noqa: PLR0913
        self: AutorunOptionsType,
        *,
        default_value: ReturnType | None = None,
        auto_await: bool | None = None,
        initial_call: bool = True,
        reactive: bool = True,
        memoization: bool = True,
        keep_ref: bool = True,
        subscribers_initial_run: bool = True,
        subscribers_keep_ref: bool = True,
    ) -> None: ...


class AutorunOptionsImplementation(Immutable, Generic[ReturnType, AutoAwait]):
    default_value: ReturnType | None = cast('None', NOT_SET)
    auto_await: AutoAwait = cast('AutoAwait', val=None)
    initial_call: bool = True
    reactive: bool = True
    memoization: bool = True
    keep_ref: bool = True
    subscribers_initial_run: bool = True
    subscribers_keep_ref: bool = True


AutorunOptions = cast('type[AutorunOptionsType]', AutorunOptionsImplementation)


class AutorunReturnType(
    Protocol,
    Generic[Args, ReturnType],
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


class MethodAutorunReturnType(
    AutorunReturnType,
    Protocol,
    Generic[MethodSelf, Args, ReturnType],
):
    def __call__(
        self: AutorunReturnType,
        self_: MethodSelf,
        *args: Args.args,
        **kwargs: Args.kwargs,
    ) -> ReturnType: ...


class AutorunDecorator(Protocol, Generic[ReturnType, SelectorOutput, AutoAwait]):
    @overload
    def __call__(
        self: AutorunDecorator[ReturnType, SelectorOutput, None],
        func: Callable[Concatenate[SelectorOutput, Args], Awaitable[ReturnType]],
    ) -> AutorunReturnType[Args, None]: ...
    @overload
    def __call__(
        self: AutorunDecorator[ReturnType, SelectorOutput, None],
        func: Callable[
            Concatenate[MethodSelf, SelectorOutput, Args],
            Awaitable[ReturnType],
        ],
    ) -> MethodAutorunReturnType[MethodSelf, Args, None]: ...

    @overload
    def __call__(
        self: AutorunDecorator[ReturnType, SelectorOutput, None],
        func: Callable[
            Concatenate[SelectorOutput, Args],
            ReturnType,
        ],
    ) -> AutorunReturnType[Args, ReturnType]: ...
    @overload
    def __call__(
        self: AutorunDecorator[ReturnType, SelectorOutput, None],
        func: Callable[
            Concatenate[MethodSelf, SelectorOutput, Args],
            ReturnType,
        ],
    ) -> MethodAutorunReturnType[MethodSelf, Args, ReturnType]: ...

    @overload
    def __call__(
        self: AutorunDecorator[ReturnType, SelectorOutput, Literal[True]],
        func: Callable[
            Concatenate[SelectorOutput, Args],
            Awaitable[ReturnType],
        ],
    ) -> AutorunReturnType[Args, None]: ...
    @overload
    def __call__(
        self: AutorunDecorator[ReturnType, SelectorOutput, Literal[True]],
        func: Callable[
            Concatenate[MethodSelf, SelectorOutput, Args],
            Awaitable[ReturnType],
        ],
    ) -> MethodAutorunReturnType[MethodSelf, Args, None]: ...

    @overload
    def __call__(
        self: AutorunDecorator[ReturnType, SelectorOutput, Literal[False]],
        func: Callable[
            Concatenate[SelectorOutput, Args],
            Awaitable[ReturnType],
        ],
    ) -> AutorunReturnType[Args, Awaitable[ReturnType]]: ...
    @overload
    def __call__(
        self: AutorunDecorator[ReturnType, SelectorOutput, Literal[False]],
        func: Callable[
            Concatenate[MethodSelf, SelectorOutput, Args],
            Awaitable[ReturnType],
        ],
    ) -> MethodAutorunReturnType[MethodSelf, Args, Awaitable[ReturnType]]: ...

    @overload
    def __call__(
        self: AutorunDecorator[ReturnType, SelectorOutput, bool],
        func: Callable[
            Concatenate[SelectorOutput, Args],
            ReturnType,
        ],
    ) -> AutorunReturnType[Args, ReturnType]: ...
    @overload
    def __call__(
        self: AutorunDecorator[ReturnType, SelectorOutput, bool],
        func: Callable[
            Concatenate[MethodSelf, SelectorOutput, Args],
            ReturnType,
        ],
    ) -> MethodAutorunReturnType[MethodSelf, Args, ReturnType]: ...


# View


class ViewOptions(Immutable, Generic[ReturnType]):
    default_value: ReturnType | None = None
    memoization: bool = True
    keep_ref: bool = True
    subscribers_initial_run: bool = True
    subscribers_keep_ref: bool = True


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
    Generic[ReturnType, SelectorOutput],
):
    @overload
    def __call__(
        self: ViewDecorator,
        func: Callable[
            Concatenate[SelectorOutput, Args],
            Awaitable[ReturnType],
        ],
    ) -> ViewReturnType[Awaitable[ReturnType], Args]: ...
    @overload
    def __call__(
        self: ViewDecorator,
        func: Callable[
            Concatenate[MethodSelf, SelectorOutput, Args],
            Awaitable[ReturnType],
        ],
    ) -> ViewReturnType[Awaitable[ReturnType], Args]: ...

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
            Concatenate[MethodSelf, SelectorOutput, Args],
            ReturnType,
        ],
    ) -> ViewReturnType[ReturnType, Args]: ...


# With Store


class WithStateDecorator(
    Protocol,
    Generic[SelectorOutput],
):
    @overload
    def __call__(
        self: WithStateDecorator,
        func: Callable[Concatenate[SelectorOutput, Args], ReturnType],
    ) -> Callable[Args, ReturnType]: ...

    @overload
    def __call__(
        self: WithStateDecorator,
        func: Callable[Concatenate[MethodSelf, SelectorOutput, Args], ReturnType],
    ) -> Callable[Concatenate[MethodSelf, Args], ReturnType]: ...


class EventSubscriber(Protocol):
    def __call__(
        self: EventSubscriber,
        event_type: type[Event],
        handler: EventHandler[Event],
        *,
        keep_ref: bool = True,
    ) -> Callable[[], None]: ...


DispatchParameters: TypeAlias = Action | InitAction | list[Action | InitAction]


class Dispatch(Protocol, Generic[State, Action, Event]):
    def __call__(
        self: Dispatch,
        *items: Action | Event | list[Action | Event],
        with_state: Callable[[State | None], Action | Event | list[Action | Event]]
        | None = None,
    ) -> None: ...


class BaseCombineReducerState(Immutable):
    combine_reducers_id: str


class CombineReducerAction(BaseAction):
    combine_reducers_id: str


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
