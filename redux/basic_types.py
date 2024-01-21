# ruff: noqa: A003, D100, D101, D102, D103, D104, D105, D107
from __future__ import annotations

from typing import Any, Callable, Generic, Sequence, TypeGuard

from immutable import Immutable
from typing_extensions import TypeVar


class BaseAction(Immutable):
    ...


class BaseEvent(Immutable):
    ...


class EventSubscriptionOptions(Immutable):
    run_async: bool = True


# Type variables
State = TypeVar('State', bound=Immutable, infer_variance=True)
Action = TypeVar('Action', bound=BaseAction, infer_variance=True)
Event = TypeVar('Event', bound=BaseEvent, infer_variance=True)
Event2 = TypeVar('Event2', bound=BaseEvent, infer_variance=True)
SelectorOutput = TypeVar('SelectorOutput', infer_variance=True)
ComparatorOutput = TypeVar('ComparatorOutput', infer_variance=True)
Comparator = Callable[[State], ComparatorOutput]
EventHandler = Callable[[Event], Any] | Callable[[], Any]


class CompleteReducerResult(Immutable, Generic[State, Action, Event]):
    state: State
    actions: Sequence[Action] | None = None
    events: Sequence[Event] | None = None


ReducerResult = CompleteReducerResult[State, Action, Event] | State
ReducerType = Callable[[State | None, Action], ReducerResult[State, Action, Event]]

AutorunOriginalReturnType = TypeVar('AutorunOriginalReturnType', infer_variance=True)

EventSubscriber = Callable[
    [Event, Callable[[Event], Any], EventSubscriptionOptions | None],
    Callable[[], None],
]


class InitializationActionError(Exception):
    def __init__(self: InitializationActionError, action: BaseAction) -> None:
        super().__init__(
            f"""The only accepted action type when state is None is "InitAction", \
action "{action}" is not allowed.""",
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
