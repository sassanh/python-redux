# ruff: noqa: D100, D101, D102, D103

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest
from immutable import Immutable

from redux.basic_types import (
    BaseAction,
    BaseEvent,
    CompleteReducerResult,
    FinishAction,
    FinishEvent,
    InitAction,
    InitializationActionError,
    StoreOptions,
)
from redux.main import Store

if TYPE_CHECKING:
    from collections.abc import Generator


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


class StoreType(Store[StateType, Action, FinishEvent]):
    @property
    def state(self: StoreType) -> StateType | None:
        return self._state


@pytest.fixture
def store() -> Generator[StoreType, None, None]:
    store = StoreType(reducer, options=StoreOptions(auto_init=True))
    yield store

    store.dispatch(FinishAction())


# These tests will timeout if they take a long time to run, indicating a performance
# issue.


def test_simple_dispatch(store: StoreType) -> None:
    count = 50000
    for _ in range(count):
        store.dispatch(IncrementAction())

    assert store.state is not None
    assert store.state.value == count


def test_dispatch_with_subscriptions(store: StoreType) -> None:
    for _ in range(1000):

        def callback(_: StateType | None) -> None:
            pass

        store._subscribe(callback)  # noqa: SLF001

    count = 400
    for _ in range(count):
        store.dispatch(IncrementAction())

    assert store.state is not None
    assert store.state.value == count


class SomeEvent(BaseEvent): ...


def event_emitting_reducer(
    state: StateType | None,
    action: Action,
) -> StateType | CompleteReducerResult[StateType, Action, SomeEvent | FinishEvent]:
    if state is None:
        if isinstance(action, InitAction):
            return StateType(value=0)
        raise InitializationActionError(action)

    if isinstance(action, IncrementAction):
        return CompleteReducerResult(
            state=replace(state, value=state.value + 1),
            events=[SomeEvent()],
        )

    return state


class EventEmittingStoreType(Store[StateType, Action, SomeEvent | FinishEvent]):
    @property
    def state(self: EventEmittingStoreType) -> StateType | None:
        return self._state


@pytest.fixture
def event_emitting_store() -> Generator[EventEmittingStoreType, None, None]:
    store = EventEmittingStoreType(
        event_emitting_reducer,
        options=StoreOptions(auto_init=True),
    )
    yield store
    store.dispatch(FinishAction())


def test_autorun_performance(store: StoreType) -> None:
    """Test autorun performance with many selectors."""
    autoruns = []
    for _ in range(100):

        @store.autorun(lambda state: state.value if state else 0)
        def reaction(_: int) -> None:
            pass

        autoruns.append(reaction)

    count = 400
    for _ in range(count):
        store.dispatch(IncrementAction())

    assert store.state is not None
    assert store.state.value == count


def test_middleware_chain_performance(store: StoreType) -> None:
    """Test middleware chain performance."""
    # Add many action middlewares
    for _ in range(50):
        store.register_action_middleware(lambda action: action)

    # Add many event middlewares
    for _ in range(50):
        store.register_event_middleware(lambda event: event)

    count = 5000
    for _ in range(count):
        store.dispatch(IncrementAction())

    assert store.state is not None
    assert store.state.value == count


def test_event_emission_performance(
    event_emitting_store: EventEmittingStoreType,
) -> None:
    """Test event emission performance."""
    # Add event listeners
    for _ in range(100):
        event_emitting_store.subscribe_event(SomeEvent, lambda _: None)

    count = 1000
    for _ in range(count):
        event_emitting_store.dispatch(IncrementAction())

    assert event_emitting_store.state is not None
    assert event_emitting_store.state.value == count
