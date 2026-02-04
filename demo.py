# ruff: noqa: D100, D101, D103, T201
from __future__ import annotations

import time

from immutable import Immutable

from redux import (
    BaseAction,
    BaseCombineReducerState,
    CombineReducerAction,
    CombineReducerRegisterAction,
    CombineReducerUnregisterAction,
    InitAction,
    InitializationActionError,
    Store,
    combine_reducers,
)
from redux.basic_types import (
    BaseEvent,
    CompleteReducerResult,
    FinishAction,
    ReducerResult,
)
from redux.main import StoreOptions


class CountAction(BaseAction): ...


class IncrementAction(CountAction): ...


class DecrementAction(CountAction): ...


class DoNothingAction(CountAction): ...


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
        raise InitializationActionError(action)
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
        raise InitializationActionError(action)
    if isinstance(action, IncrementAction):
        return CountStateType(count=state.count + 1)
    if isinstance(action, DecrementAction):
        return CountStateType(count=state.count - 1)
    return state


class SleepEvent(BaseEvent):
    duration: int


def inverse_reducer(
    state: CountStateType | None,
    action: ActionType,
) -> ReducerResult[CountStateType, ActionType, SleepEvent]:
    if state is None:
        if isinstance(action, InitAction):
            return CountStateType(count=0)
        raise InitializationActionError(action)
    if isinstance(action, IncrementAction):
        return CountStateType(count=state.count - 1)
    if isinstance(action, DecrementAction):
        return CountStateType(count=state.count + 1)
    if isinstance(action, DoNothingAction):
        return CompleteReducerResult(
            state=state,
            actions=[IncrementAction()],
            events=[SleepEvent(duration=3)],
        )
    return state


reducer, reducer_id = combine_reducers(
    state_type=StateType,
    action_type=ActionType,  # type: ignore [reportArgumentType]
    event_type=SleepEvent,  # type: ignore [reportArgumentType]
    straight=straight_reducer,
    base10=base10_reducer,
)
# >


def main() -> None:
    # Initialization <
    store = Store(
        reducer,
        StoreOptions(auto_init=True, side_effect_threads=2),
    )

    def event_handler(event: SleepEvent) -> None:
        print(f'Sleeping for {event.duration} seconds...')
        time.sleep(event.duration)

    store.subscribe_event(SleepEvent, event_handler)
    # >

    # -----

    # Subscription <
    store._subscribe(lambda state: print('Subscription state:', state))  # noqa: SLF001
    # >

    # -----

    # Autorun <
    @store.autorun(lambda state: state.base10)
    def render(base10_value: CountStateType) -> int:
        print('Autorun:', base10_value)
        return base10_value.count

    render.subscribe(print)

    print(f'Render output {render()}')

    store.dispatch(IncrementAction())
    print(f'Render output {render()}')

    store.dispatch(
        CombineReducerRegisterAction(
            combine_reducers_id=reducer_id,
            key='inverse',
            reducer=inverse_reducer,
        ),
    )

    store.dispatch(DoNothingAction())
    print(f'Render output {render()}')

    store.dispatch(
        CombineReducerUnregisterAction(
            combine_reducers_id=reducer_id,
            key='straight',
        ),
    )
    print(f'Render output {render()}')

    store.dispatch(DecrementAction())
    print(f'Render output {render()}')

    store.dispatch(FinishAction())
    # >
