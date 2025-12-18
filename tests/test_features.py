# ruff: noqa: D100, D101, D103, T201
from __future__ import annotations

import time
from typing import TYPE_CHECKING, TypeAlias

import pytest
from immutable import Immutable

from redux import CombineReducerRegisterAction, CombineReducerUnregisterAction, Store
from redux.combine_reducers import combine_reducers
from redux.main import StoreOptions

if TYPE_CHECKING:
    from redux_pytest.fixtures import StoreMonitor, StoreSnapshot

from redux.basic_types import (
    BaseAction,
    BaseCombineReducerState,
    BaseEvent,
    CombineReducerAction,
    CompleteReducerResult,
    FinishAction,
    InitAction,
    InitializationActionError,
    ReducerResult,
    ReducerType,
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


class SleepEvent(BaseEvent):
    duration: float


class PrintEvent(BaseEvent):
    message: str


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


def inverse_reducer(
    state: CountStateType | None,
    action: ActionType,
) -> ReducerResult[CountStateType, IncrementAction, SleepEvent]:
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


Reducer: TypeAlias = tuple[
    ReducerType[StateType, ActionType, SleepEvent | PrintEvent],
    str,
]


@pytest.fixture
def reducer() -> Reducer:
    return combine_reducers(
        state_type=StateType,
        action_type=ActionType,  # pyright: ignore [reportArgumentType]
        event_type=SleepEvent | PrintEvent,  # pyright: ignore [reportArgumentType]
        straight=straight_reducer,
        base10=base10_reducer,
    )


@pytest.fixture
def store(reducer: Reducer) -> Store:
    return Store(
        reducer[0],
        StoreOptions(
            side_effect_threads=2,
            action_middlewares=[lambda action: print(action) or action],
            event_middlewares=[lambda event: print(event) or event],
        ),
    )


def test_general(
    store: Store,
    reducer: Reducer,
    store_snapshot: StoreSnapshot,
    store_monitor: StoreMonitor,
) -> None:
    _, reducer_id = reducer
    store_snapshot.take(title='initialization')

    with pytest.raises(InitializationActionError):
        store.dispatch(IncrementAction())

    store_monitor.dispatched_actions.reset_mock()
    store.dispatch(InitAction())
    store_monitor.dispatched_actions.assert_called_once_with(InitAction())

    # Event Subscription
    # ------------------
    store._subscribe(lambda _: store_snapshot.take(title='subscription'))  # noqa: SLF001

    def event_handler(event: SleepEvent) -> None:
        time.sleep(event.duration)

    def event_handler_without_parameter() -> None:
        time.sleep(0.1)

    def never_called_event_handler() -> None:
        pytest.fail('This should never be called')

    store.subscribe_event(SleepEvent, event_handler)
    store.subscribe_event(
        SleepEvent,
        event_handler_without_parameter,
    )
    unsubscribe = store.subscribe_event(PrintEvent, never_called_event_handler)
    unsubscribe()

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
            combine_reducers_id=reducer_id,
            key='inverse',
            reducer=inverse_reducer,
        ),
    )

    store.dispatch(DoNothingAction())
    store_snapshot.take()

    store.dispatch(
        CombineReducerUnregisterAction(
            combine_reducers_id=reducer_id,
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
