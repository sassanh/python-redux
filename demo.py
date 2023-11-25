# ruff: noqa: D100, D101, D102, D103, D104, D107, A003, T201
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from redux import (
    BaseAction,
    BaseCombineReducerState,
    CombineReducerAction,
    CombineReducerRegisterAction,
    CombineReducerRegisterActionPayload,
    CombineReducerUnregisterAction,
    CombineReducerUnregisterActionPayload,
    Immutable,
    InitAction,
    InitializationActionError,
    combine_reducers,
    create_store,
)
from redux.basic_types import (
    BaseEvent,
    CompleteReducerResult,
    FinishAction,
    ReducerResult,
)
from redux.main import CreateStoreOptions

if TYPE_CHECKING:
    from typing_extensions import Literal


class CountAction(BaseAction):
    type: Literal['INCREMENT', 'DECREMENT', 'NOTHING']


ActionType = InitAction | FinishAction | CountAction | CombineReducerAction


class CountStateType(Immutable):
    count: int


class StateType(BaseCombineReducerState):
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


class SleepEvent(BaseEvent):
    type: Literal['SLEEP'] = 'SLEEP'
    payload: int


def inverse_reducer(
    state: CountStateType | None,
    action: ActionType,
) -> ReducerResult[CountStateType, ActionType, SleepEvent]:
    if state is None:
        if action.type == 'INIT':
            return CountStateType(count=0)
        raise InitializationActionError
    if action.type == 'INCREMENT':
        return CountStateType(count=state.count - 1)
    if action.type == 'DECREMENT':
        return CountStateType(count=state.count + 1)
    if action.type == 'NOTHING':
        return CompleteReducerResult(
            state=state,
            actions=[CountAction(type='INCREMENT')],
            events=[SleepEvent(payload=3)],
        )
    return state


reducer, reducer_id = combine_reducers(
    action_type=ActionType,
    state_type=StateType,
    straight=straight_reducer,
    base10=base10_reducer,
)
# >


def main() -> None:
    # Initialization <
    store = create_store(
        reducer,
        CreateStoreOptions(initial_run=True),
    )

    store.subscribe_event(
        'SLEEP', lambda event: print(event) or time.sleep(event.payload)
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
    def render(
        selector_result: CountStateType,
    ) -> int:
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

    store.dispatch(FinishAction())
    # >
