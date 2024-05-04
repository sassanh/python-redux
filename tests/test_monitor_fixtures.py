# ruff: noqa: D100, D101, D102, D103, D104, D107
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest
from immutable import Immutable

from redux.basic_types import (
    BaseAction,
    BaseEvent,
    CompleteReducerResult,
    CreateStoreOptions,
    FinishAction,
    FinishEvent,
    InitAction,
    InitializationActionError,
)
from redux.main import Store

if TYPE_CHECKING:
    from redux_pytest.fixtures.monitor import StoreMonitor
    from redux_pytest.fixtures.snapshot import StoreSnapshot
    from redux_pytest.fixtures.wait_for import WaitFor


class StateType(Immutable):
    value: int
    mirrored_value: int


class IncrementAction(BaseAction): ...


class DummyEvent(BaseEvent): ...


Action = IncrementAction | InitAction | FinishAction


def reducer(
    state: StateType | None,
    action: Action,
) -> StateType | CompleteReducerResult[StateType, Action, DummyEvent | FinishEvent]:
    if state is None:
        if isinstance(action, InitAction):
            return StateType(value=0, mirrored_value=0)
        raise InitializationActionError(action)

    if isinstance(action, IncrementAction):
        return replace(state, value=state.value + 1)
    return state


@pytest.fixture()
def store() -> Store:
    return Store(
        reducer,
        options=CreateStoreOptions(
            auto_init=True,
        ),
    )


def test_monitor_action(
    store: Store,
    store_monitor: StoreMonitor,
    needs_finish: None,
) -> None:
    _ = needs_finish
    store.dispatch(IncrementAction())
    store_monitor.dispatched_actions.assert_called_once_with(IncrementAction())


def test_monitor_event(
    store: Store,
    store_monitor: StoreMonitor,
    needs_finish: None,
) -> None:
    _ = needs_finish
    store.dispatch(DummyEvent())
    store_monitor.dispatched_events.assert_called_once_with(DummyEvent())


def test_multiple_stores(
    store: Store,
    store_monitor: StoreMonitor,
    needs_finish: None,
) -> None:
    _ = needs_finish
    store = Store(
        reducer,
        options=CreateStoreOptions(
            auto_init=True,
        ),
    )

    store.dispatch(IncrementAction())
    store_monitor.dispatched_actions.assert_not_called()

    store_monitor.monitor(store)
    store.dispatch(IncrementAction())
    store_monitor.dispatched_actions.assert_called_once_with(IncrementAction())

    store.dispatch(FinishAction())


def test_closed_snapshot_store(
    store_snapshot: StoreSnapshot,
    wait_for: WaitFor,
    store: Store,
) -> None:
    store.dispatch(FinishAction())

    @wait_for
    def is_closed() -> None:
        assert store_snapshot._is_closed  # noqa: SLF001
        with pytest.raises(
            RuntimeError,
            match='^Snapshot context is closed, make sure you are not calling `take` '
            'after `FinishEvent` is dispatched.$',
        ):
            store_snapshot.take()

    is_closed()
