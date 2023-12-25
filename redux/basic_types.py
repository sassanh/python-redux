# ruff: noqa: A003, D100, D101, D102, D103, D104, D105, D107
from __future__ import annotations

from typing import (
    Any,
    Callable,
    Generic,
    TypeGuard,
    TypeVar,
)

from immutable import Immutable


class BaseAction(Immutable):
    ...


class BaseEvent(Immutable):
    ...


class EventSubscriptionOptions(Immutable):
    run_async: bool = True


# Type variables
State = TypeVar('State', bound=Immutable)
State_co = TypeVar('State_co', bound=Immutable, covariant=True)
Action = TypeVar('Action', bound=BaseAction)
SelectorOutput = TypeVar('SelectorOutput')
SelectorOutput_co = TypeVar('SelectorOutput_co', covariant=True)
SelectorOutput_contra = TypeVar('SelectorOutput_contra', contravariant=True)
ComparatorOutput = TypeVar('ComparatorOutput')
Selector = Callable[[State], SelectorOutput]
Comparator = Callable[[State], ComparatorOutput]
Event = TypeVar('Event', bound=BaseEvent)
EventHandler = Callable[[Event], Any]


class CompleteReducerResult(Immutable, Generic[State, Action, Event]):
    state: State
    actions: list[Action] | None = None
    events: list[Event] | None = None


ReducerResult = CompleteReducerResult[State, Action, Event] | State
ReducerType = Callable[[State | None, Action], ReducerResult[State, Action, Event]]

AutorunOriginalReturnType = TypeVar('AutorunOriginalReturnType')
AutorunOriginalReturnType_co = TypeVar('AutorunOriginalReturnType_co', covariant=True)

EventSubscriber = Callable[
    [Event, Callable[[Event], Any], EventSubscriptionOptions | None],
    Callable[[], None],
]


class InitializationActionError(Exception):
    def __init__(self: InitializationActionError) -> None:
        super().__init__(
            'The only accepted action type when state is None is "InitAction"',
        )


class InitAction(BaseAction):
    ...


class FinishAction(BaseAction):
    ...


class FinishEvent(BaseEvent):
    ...


def is_reducer_result(
    result: ReducerResult[State, Action, Event],
) -> TypeGuard[CompleteReducerResult[State, Action, Event]]:
    return isinstance(result, CompleteReducerResult)


def is_state(result: ReducerResult[State, Action, Event]) -> TypeGuard[State]:
    return not isinstance(result, CompleteReducerResult)
