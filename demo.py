# ruff: noqa: D100, D101, D102, D103, D104, D107
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict

from redux import (
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


class CountStateType(TypedDict):
    count: int


class StateType(TypedDict):
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
            return {'count': 0}
        raise InitializationActionError
    if action.type == 'INCREMENT':
        return {**state, 'count': state['count'] + 1}
    if action.type == 'DECREMENT':
        return {**state, 'count': state['count'] - 1}
    return state


def base10_reducer(
    state: CountStateType | None,
    action: ActionType,
) -> CountStateType:
    if state is None:
        if action.type == 'INIT':
            return {'count': 10}
        raise InitializationActionError
    if action.type == 'INCREMENT':
        return {**state, 'count': state['count'] + 1}
    if action.type == 'DECREMENT':
        return {**state, 'count': state['count'] - 1}
    return state


def inverse_reducer(
    state: CountStateType | None,
    action: ActionType,
) -> CountStateType:
    if state is None:
        if action.type == 'INIT':
            return {'count': 0}
        raise InitializationActionError
    if action.type == 'INCREMENT':
        return {**state, 'count': state['count'] - 1}
    if action.type == 'DECREMENT':
        return {**state, 'count': state['count'] + 1}
    return state


reducer: ReducerType[StateType, ActionType]
reducer, reducer_id = combine_reducers(
    straight=straight_reducer,
    base10=base10_reducer,
)
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
    @store.autorun(lambda state: state['base10'])
    def render(state: StateType, old_state: StateType):  # noqa: ANN202
        print('Autorun:', state, old_state)

    store.dispatch(CountAction(type='INCREMENT'))

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

    store.dispatch(
        CombineReducerUnregisterAction(
            type='UNREGISTER',
            _id=reducer_id,
            payload=CombineReducerUnregisterActionPayload(
                key='straight',
            ),
        ),
    )

    store.dispatch(CountAction(type='DECREMENT'))
    # >
