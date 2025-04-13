# ruff: noqa: D100, D101, D102, D103, D104, D107

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

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
