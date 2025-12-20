# ruff: noqa: D100, D101, D103
from __future__ import annotations

from dataclasses import replace

import pytest
from immutable import Immutable

from redux.basic_types import (
    BaseAction,
    CompleteReducerResult,
    FinishAction,
    FinishEvent,
    InitAction,
    InitializationActionError,
    StoreOptions,
)
from redux.main import Store


class StateType(Immutable):
    value: int


class IncrementAction(BaseAction): ...


Action = IncrementAction | InitAction | FinishAction


def reducer(
    state: StateType | None,
    action: Action,
) -> StateType | CompleteReducerResult[StateType, Action, FinishEvent]:
    if state is None:
        if isinstance(action, InitAction):
            return StateType(value=0)
        raise InitializationActionError(action)

    if isinstance(action, IncrementAction):
        return replace(state, value=state.value + 1)

    return state


StoreType = Store[StateType, Action, FinishEvent]


@pytest.fixture
def store() -> StoreType:
    return Store(reducer, options=StoreOptions(auto_init=True))


def test_general(store: StoreType) -> None:
    times_called = 0

    def callback(state: StateType | None) -> None:
        nonlocal times_called
        times_called += 1
        assert state is not None
        assert state.value == times_called

    unsubscribe = store._subscribe(callback)  # noqa: SLF001
    for _ in range(5):
        store.dispatch(IncrementAction())
    unsubscribe()
    for _ in range(5):
        store.dispatch(IncrementAction())

    store.dispatch(FinishAction())

    assert times_called == 5


def test_not_keeping_ref_keeping_callback(store: StoreType) -> None:
    times_called = 0

    def callback(state: StateType | None) -> None:
        nonlocal times_called
        times_called += 1
        assert state is not None
        assert state.value == times_called

    unsubscribe = store._subscribe(callback, keep_ref=False)  # noqa: SLF001
    for _ in range(5):
        store.dispatch(IncrementAction())
    unsubscribe()
    for _ in range(5):
        store.dispatch(IncrementAction())

    store.dispatch(FinishAction())

    assert times_called == 5


def test_keeping_ref_with_callback_deletion(store: StoreType) -> None:
    times_called = 0

    def callback(state: StateType | None) -> None:
        nonlocal times_called
        times_called += 1
        assert state is not None
        assert state.value == times_called

    unsubscribe = store._subscribe(callback)  # noqa: SLF001
    del callback

    for _ in range(5):
        store.dispatch(IncrementAction())
    unsubscribe()
    for _ in range(5):
        store.dispatch(IncrementAction())

    store.dispatch(FinishAction())

    assert times_called == 5


def test_not_keeping_ref_with_callback_deletion(store: StoreType) -> None:
    times_called = 0

    def callback(state: StateType | None) -> None:
        nonlocal times_called
        times_called += 1
        assert state is not None
        assert state.value == times_called

    store._subscribe(callback, keep_ref=False)  # noqa: SLF001

    for _ in range(5):
        store.dispatch(IncrementAction())
    del callback
    for _ in range(5):
        store.dispatch(IncrementAction())

    store.dispatch(FinishAction())

    assert times_called == 5
