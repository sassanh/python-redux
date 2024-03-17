# ruff: noqa: A003, D100, D101, D102, D103, D104, D105, D107
from __future__ import annotations

from types import NoneType
from typing import TYPE_CHECKING, Any, Callable, Generic, Protocol, TypeAlias, TypeGuard

from immutable import Immutable
from typing_extensions import TypeVar

if TYPE_CHECKING:
    import asyncio


class BaseAction(Immutable): ...


class BaseEvent(Immutable): ...


class EventSubscriptionOptions(Immutable):
    immediate_run: bool = False
    keep_ref: bool = True


# Type variables
State = TypeVar('State', bound=Immutable, infer_variance=True)
Action = TypeVar('Action', bound=BaseAction, infer_variance=True)
Event = TypeVar('Event', bound=BaseEvent, infer_variance=True)
Event2 = TypeVar('Event2', bound=BaseEvent, infer_variance=True)
SelectorOutput = TypeVar('SelectorOutput', infer_variance=True)
ComparatorOutput = TypeVar('ComparatorOutput', infer_variance=True)
AutorunOriginalReturnType = TypeVar('AutorunOriginalReturnType', infer_variance=True)
Comparator = Callable[[State], ComparatorOutput]
EventHandler = Callable[[Event], Any] | Callable[[], Any]


class CompleteReducerResult(Immutable, Generic[State, Action, Event]):
    state: State
    actions: list[Action] | None = None
    events: list[Event] | None = None


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


class CreateStoreOptions(Immutable):
    auto_init: bool = False
    threads: int = 5
    scheduler: Scheduler | None = None
    action_middleware: Callable[[BaseAction], Any] | None = None
    event_middleware: Callable[[BaseEvent], Any] | None = None
    async_loop: asyncio.AbstractEventLoop | None = None


class AutorunOptions(Immutable, Generic[AutorunOriginalReturnType]):
    default_value: AutorunOriginalReturnType | None = None
    initial_run: bool = True
    keep_ref: bool = True
    subscribers_initial_run: bool = True
    subscribers_keep_ref: bool = True


class AutorunType(Protocol, Generic[State]):
    def __call__(
        self: AutorunType,
        selector: Callable[[State], SelectorOutput],
        comparator: Callable[[State], Any] | None = None,
        *,
        options: AutorunOptions[AutorunOriginalReturnType] | None = None,
    ) -> AutorunDecorator[
        State,
        SelectorOutput,
        AutorunOriginalReturnType,
    ]: ...


class AutorunDecorator(
    Protocol,
    Generic[
        State,
        SelectorOutput,
        AutorunOriginalReturnType,
    ],
):
    def __call__(
        self: AutorunDecorator,
        func: Callable[[SelectorOutput], AutorunOriginalReturnType]
        | Callable[[SelectorOutput, SelectorOutput], AutorunOriginalReturnType],
    ) -> AutorunReturnType[AutorunOriginalReturnType]: ...


class AutorunReturnType(
    Protocol,
    Generic[AutorunOriginalReturnType],
):
    def __call__(self: AutorunReturnType) -> AutorunOriginalReturnType: ...

    @property
    def value(self: AutorunReturnType) -> AutorunOriginalReturnType: ...

    def subscribe(
        self: AutorunReturnType,
        callback: Callable[[AutorunOriginalReturnType], Any],
        *,
        initial_run: bool | None = None,
        keep_ref: bool | None = None,
    ) -> Callable[[], None]: ...


class EventSubscriber(Protocol):
    def __call__(
        self: EventSubscriber,
        event_type: type[Event],
        handler: EventHandler[Event],
        *,
        options: EventSubscriptionOptions | None = None,
    ) -> Callable[[], None]: ...


DispatchParameters: TypeAlias = Action | Event | list[Action | Event]


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


class CombineReducerInitAction(CombineReducerAction, InitAction):
    key: str


class CombineReducerRegisterAction(CombineReducerAction):
    key: str
    reducer: ReducerType


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
