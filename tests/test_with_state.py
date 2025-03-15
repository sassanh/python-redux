"""Tests for `with_state` decorator."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest
from immutable import Immutable

from redux.basic_types import (
    BaseAction,
    CreateStoreOptions,
    FinishAction,
    FinishEvent,
    InitAction,
    InitializationActionError,
)
from redux.main import Store

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


class _StateType(Immutable):
    value: int


class _IncrementAction(BaseAction): ...


Action = _IncrementAction | InitAction | FinishAction

StoreType = Store[_StateType, Action, FinishEvent]


def _reducer(
    state: _StateType | None,
    action: Action,
) -> _StateType:
    if state is None:
        if isinstance(action, InitAction):
            return _StateType(value=0)
        raise InitializationActionError(action)

    if isinstance(action, _IncrementAction):
        return replace(state, value=state.value + 1)

    return state


@pytest.fixture(name='store')
def _() -> StoreType:
    return Store(_reducer, options=CreateStoreOptions(auto_init=False))


def test_with_state(store: StoreType) -> None:
    """Test `with_state` decorator."""
    counter = 0

    @store.with_state(lambda state: state.value)
    def check(value: int) -> int:
        nonlocal counter

        assert value == counter

        counter += 1

        return value

    store.dispatch(InitAction())

    for i in range(10):
        assert check() == i
        store.dispatch(_IncrementAction())

    store.dispatch(FinishAction())


def test_with_state_for_uninitialized_store(
    store: StoreType,
    mocker: MockerFixture,
) -> None:
    """Test `with_state` decorator for uninitialized store."""

    class X:
        def check(self: X, value: int) -> None:
            assert value == 0

    instance = X()

    check_spy = mocker.spy(instance, 'check')
    check = store.with_state(lambda state: state.value)(instance.check)

    with pytest.raises(RuntimeError, match=r'^Store has not been initialized yet.$'):
        check()

    store.dispatch(InitAction())

    check()

    store.dispatch(FinishAction())

    check_spy.assert_called_once_with(0)
