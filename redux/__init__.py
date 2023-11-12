# ruff: noqa: D101, D102, D103, D104, D107
from __future__ import annotations

from dataclasses import dataclass
from inspect import signature
from typing import (
    Any,
    Callable,
    Generic,
    Literal,
    Mapping,
    Sequence,
    TypedDict,
    TypeVar,
    cast,
)


class InitializationActionError(Exception):
    def __init__(self: InitializationActionError) -> None:
        super().__init__(
            'The only accepted action type when state is None is "INIT"',
        )


# Type variables
State = TypeVar('State', bound=Mapping[str, Any])
State_co = TypeVar('State_co', covariant=True)
Action = TypeVar('Action')
ParamsType = TypeVar('ParamsType')
ReturnType = TypeVar('ReturnType')
Selector = Callable[[State], Any]
ReducerType = Callable[[State | None, Action], State]


@dataclass
class BaseAction:
    ...


@dataclass
class InitAction(BaseAction):
    type: Literal['INIT'] = 'INIT'


class Options(TypedDict):
    initial_run: bool | None


@dataclass
class InitializeStateReturnValue(Generic[State, Action]):
    dispatch: Callable[[Action | list[Action]], None]
    subscribe: Callable[[Callable[[State], None]], Callable[[], None]]


def create_store(
    reducer: ReducerType[State, Action],
    options: Options | None = None,
) -> InitializeStateReturnValue[State, Action]:
    options = options or {'initial_run': True}

    state: State | None = None
    listeners: set[Callable[[State], None]] = set()

    def dispatch(actions: Action | Sequence[Action]) -> None:
        nonlocal state, reducer, listeners
        if not isinstance(actions, Sequence):
            actions = [actions]
        actions = cast(Sequence[Action], actions)
        if len(actions) == 0:
            return
        state = reducer(state, actions[0])
        for action in actions[1:]:
            state = reducer(state, action)
        for listener in listeners:
            listener(state)

    def subscribe(listener: Callable[[State], None]) -> Callable[[], None]:
        nonlocal listeners
        listeners.add(listener)
        return lambda: listeners.remove(listener)

    return InitializeStateReturnValue(
        dispatch=dispatch,
        subscribe=subscribe,
    )
