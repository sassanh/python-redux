# ruff: noqa: D100, D101, D102, D103, D104, D107
from __future__ import annotations

import time
from typing import TYPE_CHECKING, TypeAlias

import pytest
from immutable import Immutable

if TYPE_CHECKING:
    from redux.test import StoreSnapshotContext

from redux.basic_types import (
    BaseAction,
    BaseCombineReducerState,
    BaseEvent,
    CombineReducerAction,
    CompleteReducerResult,
    EventSubscriptionOptions,
    FinishAction,
    InitAction,
    InitializationActionError,
    ReducerResult,
)


class CountAction(BaseAction): ...


class IncrementAction(CountAction): ...


class DecrementByTwoAction(CountAction): ...


class DoNothingAction(CountAction): ...


class CountStateType(Immutable):
    count: int


class StateType(BaseCombineReducerState):
    straight: CountStateType
    base10: CountStateType
    inverse: CountStateType


ActionType: TypeAlias = InitAction | FinishAction | CountAction | CombineReducerAction


# Reducers
# --------
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
    if isinstance(action, DecrementByTwoAction):
        return CountStateType(count=state.count - 2)
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
    if isinstance(action, DecrementByTwoAction):
        return CountStateType(count=state.count - 2)
    return state


class SleepEvent(BaseEvent):
    duration: float


class PrintEvent(BaseEvent):
    message: str


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
    if isinstance(action, DecrementByTwoAction):
        return CountStateType(count=state.count + 2)
    if isinstance(action, DoNothingAction):
        return CompleteReducerResult(
            state=state,
            actions=[IncrementAction()],
            events=[SleepEvent(duration=0.1)],
        )
    return state


def test_general(store_snapshot: StoreSnapshotContext) -> None:
    from redux import (
        CombineReducerRegisterAction,
        CombineReducerUnregisterAction,
        Store,
    )
    from redux.combine_reducers import combine_reducers
    from redux.main import CreateStoreOptions

    reducer, reducer_id = combine_reducers(
        state_type=StateType,
        action_type=ActionType,  # pyright: ignore [reportArgumentType]
        event_type=SleepEvent | PrintEvent,  # pyright: ignore [reportArgumentType]
        straight=straight_reducer,
        base10=base10_reducer,
    )

    # Initialization
    # --------------
    store = Store(
        reducer,
        CreateStoreOptions(threads=2, action_middleware=print, event_middleware=print),
    )
    store_snapshot.set_store(store)

    store_snapshot.take(title='initialization')

    with pytest.raises(InitializationActionError):
        store.dispatch(IncrementAction())

    store.dispatch(InitAction())

    # Event Subscription
    # ------------------
    store.subscribe(lambda _: store_snapshot.take(title='subscription'))

    def event_handler(event: SleepEvent) -> None:
        time.sleep(event.duration)

    def event_handler_without_parameter() -> None:
        time.sleep(0.1)

    store.subscribe_event(SleepEvent, event_handler)
    store.subscribe_event(
        SleepEvent,
        event_handler_without_parameter,
        options=EventSubscriptionOptions(immediate_run=True),
    )

    # Autorun
    # -------

    @store.autorun(lambda state: state.base10)
    def render(base10_value: CountStateType) -> int:
        store_snapshot.take(title='autorun')
        return base10_value.count

    render.subscribe(lambda _: store_snapshot.take(title='autorun_subscription'))

    # Dispatch
    # --------
    store_snapshot.take()

    store.dispatch(IncrementAction())
    store_snapshot.take()

    store.dispatch(
        CombineReducerRegisterAction(
            _id=reducer_id,
            key='inverse',
            reducer=inverse_reducer,
        ),
    )

    store.dispatch(DoNothingAction())
    store_snapshot.take()

    store.dispatch(
        CombineReducerUnregisterAction(
            _id=reducer_id,
            key='straight',
        ),
    )
    store_snapshot.take()

    store.dispatch(DecrementByTwoAction())
    store_snapshot.take()

    store.dispatch(
        with_state=lambda state: DecrementByTwoAction() if state else IncrementAction(),
    )
    store_snapshot.take()
    # Finish
    # ------
    store.dispatch(FinishAction())
