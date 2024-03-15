# ruff: noqa: D100, D101, D102, D103, D104, D107, A003, T201
from __future__ import annotations

import time
from typing import TYPE_CHECKING, TypeAlias

from immutable import Immutable

if TYPE_CHECKING:
    from logging import Logger

    from redux.test import StoreSnapshotContext

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
)


class CountAction(BaseAction):
    ...


class IncrementAction(CountAction):
    ...


class DecrementAction(CountAction):
    ...


class DoNothingAction(CountAction):
    ...


class CountStateType(Immutable):
    count: int


class StateType(BaseCombineReducerState):
    straight: CountStateType
    base10: CountStateType
    inverse: CountStateType


ActionType: TypeAlias = InitAction | FinishAction | CountAction | CombineReducerAction


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
    if isinstance(action, DecrementAction):
        return CountStateType(count=state.count + 1)
    if isinstance(action, DoNothingAction):
        return CompleteReducerResult(
            state=state,
            actions=[IncrementAction()],
            events=[SleepEvent(duration=3)],
        )
    return state


# >


def test_general(snapshot_store: StoreSnapshotContext, logger: Logger) -> None:
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

    # Initialization <
    store = Store(
        reducer,
        CreateStoreOptions(auto_init=True, threads=2),
    )
    snapshot_store.set_store(store)

    def event_handler(event: SleepEvent) -> None:
        time.sleep(event.duration)

    store.subscribe_event(SleepEvent, event_handler)
    # >

    # -----

    # Subscription <
    store.subscribe(lambda _: snapshot_store.take())
    # >

    # -----

    # Autorun <
    @store.autorun(lambda state: state.base10)
    def render(base10_value: CountStateType) -> int:
        snapshot_store.take()
        return base10_value.count

    render.subscribe(lambda a: logger.info(a))

    snapshot_store.take()

    store.dispatch(IncrementAction())
    snapshot_store.take()

    store.dispatch(
        CombineReducerRegisterAction(
            _id=reducer_id,
            key='inverse',
            reducer=inverse_reducer,
        ),
    )

    store.dispatch(DoNothingAction())
    snapshot_store.take()

    store.dispatch(
        CombineReducerUnregisterAction(
            _id=reducer_id,
            key='straight',
        ),
    )
    snapshot_store.take()

    store.dispatch(DecrementAction())
    snapshot_store.take()

    store.dispatch(FinishAction())
    # >
