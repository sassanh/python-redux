# ruff: noqa: D102
"""Benchmarks for python-redux Store operations."""

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
    InitAction,
    InitializationActionError,
    StoreOptions,
)
from redux.main import Store

if TYPE_CHECKING:
    from collections.abc import Generator


# --------------------------------------------------------------------------
# State and Actions
# --------------------------------------------------------------------------


class BenchState(Immutable):
    """Simple state for benchmarking."""

    value: int


class IncrementAction(BaseAction):
    """Increment the counter."""


class IncrementByAction(BaseAction):
    """Increment by a specific amount."""

    amount: int


class DummyEvent(BaseEvent):
    """Dummy event for event handler benchmarks."""


Action = IncrementAction | IncrementByAction | InitAction | FinishAction


# --------------------------------------------------------------------------
# Reducer
# --------------------------------------------------------------------------


def reducer(
    state: BenchState | None,
    action: Action,
) -> BenchState | CompleteReducerResult[BenchState, Action, DummyEvent]:
    if state is None:
        if isinstance(action, InitAction):
            return BenchState(value=0)
        raise InitializationActionError(action)

    if isinstance(action, IncrementAction):
        return replace(state, value=state.value + 1)

    if isinstance(action, IncrementByAction):
        return replace(state, value=state.value + action.amount)

    return state


# --------------------------------------------------------------------------
# Store Fixture
# --------------------------------------------------------------------------


class BenchStore(Store[BenchState, Action, DummyEvent]):
    """Store subclass exposing state for assertions."""

    @property
    def state(self) -> BenchState | None:
        return self._state


@pytest.fixture
def store() -> Generator[BenchStore, None, None]:
    """Create a store for benchmarking."""
    store = BenchStore(reducer, options=StoreOptions(auto_init=True))
    yield store
    store.dispatch(FinishAction())


# --------------------------------------------------------------------------
# Benchmarks
# --------------------------------------------------------------------------


def test_dispatch_simple(benchmark, store: BenchStore) -> None:
    """Benchmark simple dispatch throughput."""

    def run() -> None:
        for _ in range(1000):
            store.dispatch(IncrementAction())

    benchmark(run)
    assert store.state is not None
    assert store.state.value > 0


def test_dispatch_with_payload(benchmark, store: BenchStore) -> None:
    """Benchmark dispatch with action payload."""

    def run() -> None:
        for _ in range(1000):
            store.dispatch(IncrementByAction(amount=5))

    benchmark(run)
    assert store.state is not None


def test_dispatch_batch(benchmark, store: BenchStore) -> None:
    """Benchmark batch dispatch (list of actions)."""
    actions = [IncrementAction() for _ in range(100)]

    def run() -> None:
        for _ in range(10):
            store.dispatch(*actions)

    benchmark(run)
    assert store.state is not None


def test_dispatch_with_subscribers(benchmark, store: BenchStore) -> None:
    """Benchmark dispatch with many subscribers."""
    # Add 100 subscribers
    for _ in range(100):

        def callback(_: BenchState | None) -> None:
            pass

        store._subscribe(callback)  # noqa: SLF001

    def run() -> None:
        for _ in range(100):
            store.dispatch(IncrementAction())

    benchmark(run)
    assert store.state is not None


def test_dispatch_with_event_handlers(benchmark) -> None:
    """Benchmark dispatch with event handlers."""
    store = BenchStore(reducer, options=StoreOptions(auto_init=True))

    events_received = [0]

    def event_handler(_: DummyEvent) -> None:
        events_received[0] += 1

    store.subscribe_event(DummyEvent, event_handler)

    # Create reducer that emits events
    def reducer_with_events(
        state: BenchState | None,
        action: Action,
    ) -> BenchState | CompleteReducerResult[BenchState, Action, DummyEvent]:
        if state is None:
            if isinstance(action, InitAction):
                return BenchState(value=0)
            raise InitializationActionError(action)

        if isinstance(action, IncrementAction):
            return CompleteReducerResult(
                state=replace(state, value=state.value + 1),
                events=[DummyEvent()],
            )
        return state

    store_with_events = BenchStore(
        reducer_with_events,
        options=StoreOptions(auto_init=True),
    )
    store_with_events.subscribe_event(DummyEvent, event_handler)

    def run() -> None:
        for _ in range(100):
            store_with_events.dispatch(IncrementAction())

    benchmark(run)

    store.dispatch(FinishAction())
    store_with_events.dispatch(FinishAction())


# --------------------------------------------------------------------------
# Standalone benchmark runner
# --------------------------------------------------------------------------


def run_benchmark() -> None:
    """Run benchmarks standalone for profiling."""
    store = BenchStore(reducer, options=StoreOptions(auto_init=True))

    # Simple dispatch
    for _ in range(50000):
        store.dispatch(IncrementAction())

    store.dispatch(FinishAction())


if __name__ == '__main__':
    run_benchmark()
