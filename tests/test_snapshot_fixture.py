# ruff: noqa: D100, D101, D102, D103, D104, D107
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest
from immutable import Immutable

from redux.basic_types import (
    BaseAction,
    BaseEvent,
    FinishAction,
    FinishEvent,
    InitAction,
    InitializationActionError,
    ReducerResult,
    StoreOptions,
)
from redux.main import Store

if TYPE_CHECKING:
    from redux_pytest.fixtures.snapshot import StoreSnapshot


class StateType(Immutable):
    value: int


class IncrementAction(BaseAction): ...


class DummyEvent(BaseEvent): ...


Action = InitAction | IncrementAction | FinishAction


def reducer(
    state: StateType | None,
    action: Action,
) -> ReducerResult[StateType, Action, DummyEvent | FinishEvent]:
    if state is None:
        if isinstance(action, InitAction):
            return StateType(value=0)
        raise InitializationActionError(action)

    if isinstance(action, IncrementAction):
        return replace(state, value=state.value + 1)
    return state


@pytest.fixture
def store() -> Store:
    return Store(reducer, options=StoreOptions(auto_init=True))


def test_monitor(
    store: Store,
    store_snapshot: StoreSnapshot[StateType],
    needs_finish: None,
) -> None:
    _ = needs_finish
    store_snapshot.monitor(lambda state: state.value if state.value % 2 != 0 else None)
    store.dispatch(IncrementAction())
    store.dispatch(IncrementAction())
    store.dispatch(IncrementAction())
    store.dispatch(IncrementAction())


class TestSnapshotPrefix:
    @pytest.fixture(scope='class')
    def snapshot_prefix(self: TestSnapshotPrefix) -> str:
        return 'custom_prefix'

    def test_prefix(
        self: TestSnapshotPrefix,
        store: Store,
        store_snapshot: StoreSnapshot[StateType],
        needs_finish: None,
    ) -> None:
        _ = needs_finish
        store_snapshot.monitor(lambda state: state.value)
        store.dispatch(IncrementAction())
