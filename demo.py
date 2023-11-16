# ruff: noqa: D100, D101, D102, D103, D104, D107
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from redux import (
    BaseState,
    CombineReducerAction,
    CombineReducerRegisterAction,
    CombineReducerRegisterActionPayload,
    CombineReducerUnregisterAction,
    CombineReducerUnregisterActionPayload,
    InitAction,
    InitializationActionError,
    ReducerType,
    combine_reducers,
    create_store,
)

if TYPE_CHECKING:
    from typing_extensions import Literal


@dataclass
class CountAction:
    type: Literal['INCREMENT', 'DECREMENT', 'NOTHING']


ActionType = InitAction | CountAction | CombineReducerAction


@dataclass(frozen=True)
class CountStateType:
    count: int


@dataclass(frozen=True)
class StateType(BaseState):
    straight: CountStateType
    base10: CountStateType
    inverse: CountStateType


# Reducers <
def straight_reducer(
    state: CountStateType | None,
    action: ActionType,
) -> CountStateType:
    if state is None:
        if action.type == 'INIT':
            return CountStateType(count=0)
        raise InitializationActionError
    if action.type == 'INCREMENT':
        return CountStateType(count=state.count + 1)
    if action.type == 'DECREMENT':
        return CountStateType(count=state.count - 1)
    return state


def base10_reducer(
    state: CountStateType | None,
    action: ActionType,
) -> CountStateType:
    if state is None:
        if action.type == 'INIT':
            return CountStateType(count=10)
        raise InitializationActionError
    if action.type == 'INCREMENT':
        return CountStateType(count=state.count + 1)
    if action.type == 'DECREMENT':
        return CountStateType(count=state.count - 1)
    return state


def inverse_reducer(
    state: CountStateType | None,
    action: ActionType,
) -> CountStateType:
    if state is None:
        if action.type == 'INIT':
            return CountStateType(count=0)
        raise InitializationActionError
    if action.type == 'INCREMENT':
        return CountStateType(count=state.count - 1)
    if action.type == 'DECREMENT':
        return CountStateType(count=state.count + 1)
    return state


reducer, reducer_id = combine_reducers(
    straight=straight_reducer,
    base10=base10_reducer,
)
reducer = cast(ReducerType[StateType, ActionType], reducer)
# >


def main() -> None:
    # Initialization <
    store = create_store(
        reducer,
        {'initial_run': True},
    )

    store.dispatch(InitAction(type='INIT'))
    # >

    # -----

    # Subscription <
    store.subscribe(lambda state: print('Subscripton state:', state))
    # >

    # -----

    # Autorun <
    @store.autorun(lambda state: state.base10)
    def render(selector_result: CountStateType) -> int:
        print('Autorun:', selector_result)
        return selector_result.count

    print(f'Render output {render()}')

    store.dispatch(CountAction(type='INCREMENT'))
    print(f'Render output {render()}')

    store.dispatch(
        CombineReducerRegisterAction(
            type='REGISTER',
            _id=reducer_id,
            payload=CombineReducerRegisterActionPayload(
                key='inverse',
                reducer=inverse_reducer,
            ),
        ),
    )

    store.dispatch(CountAction(type='NOTHING'))
    print(f'Render output {render()}')

    store.dispatch(
        CombineReducerUnregisterAction(
            type='UNREGISTER',
            _id=reducer_id,
            payload=CombineReducerUnregisterActionPayload(
                key='straight',
            ),
        ),
    )
    print(f'Render output {render()}')

    store.dispatch(CountAction(type='DECREMENT'))
    print(f'Render output {render()}')
    # >
