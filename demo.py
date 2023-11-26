# ruff: noqa: D100, D101, D102, D103, D104, D107, A003, T201
from __future__ import annotations

import time

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


class CountAction(BaseAction):
    ...


class IncrementAction(CountAction):
    ...


class DecrementAction(CountAction):
    ...


class NothingAction(CountAction):
    ...


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
        if isinstance(action, InitAction):
            return CountStateType(count=0)
        raise InitializationActionError
    if isinstance(action, IncrementAction):
        return CountStateType(count=state.count + 1)
    if isinstance(action, DecrementAction):
        return CountStateType(count=state.count - 1)
    return state


def base10_reducer(
    state: CountStateType | None,
    action: ActionType,
) -> CountStateType:
    if state is None:
        if isinstance(action, InitAction):
            return CountStateType(count=10)
        raise InitializationActionError
    if isinstance(action, IncrementAction):
        return CountStateType(count=state.count + 1)
    if isinstance(action, DecrementAction):
        return CountStateType(count=state.count - 1)
    return state


class SleepEvent(BaseEvent):
    payload: int


class PrintEvent(BaseEvent):
    payload: str


def inverse_reducer(
    state: CountStateType | None,
    action: ActionType,
) -> ReducerResult[CountStateType, ActionType, SleepEvent]:
    if state is None:
        if isinstance(action, InitAction):
            return CountStateType(count=0)
        raise InitializationActionError
    if isinstance(action, IncrementAction):
        return CountStateType(count=state.count - 1)
    if isinstance(action, DecrementAction):
        return CountStateType(count=state.count + 1)
    if isinstance(action, NothingAction):
        return CompleteReducerResult(
            state=state,
            actions=[IncrementAction()],
            events=[SleepEvent(payload=3)],
        )
    return state


reducer, reducer_id = combine_reducers(
    state_type=StateType,
    action_type=ActionType,
    event_type=SleepEvent | PrintEvent,
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

    def event_handler(event: SleepEvent) -> None:
        time.sleep(event.payload)

    store.subscribe_event(SleepEvent, event_handler)

    store.dispatch(InitAction())
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

    store.dispatch(IncrementAction())
    print(f'Render output {render()}')

    store.dispatch(
        CombineReducerRegisterAction(
            _id=reducer_id,
            payload=CombineReducerRegisterActionPayload(
                key='inverse',
                reducer=inverse_reducer,
            ),
        ),
    )

    store.dispatch(NothingAction())
    print(f'Render output {render()}')

    store.dispatch(
        CombineReducerUnregisterAction(
            _id=reducer_id,
            payload=CombineReducerUnregisterActionPayload(
                key='straight',
            ),
        ),
    )
    print(f'Render output {render()}')

    store.dispatch(DecrementAction())
    print(f'Render output {render()}')

    store.dispatch(FinishAction())
    # >
