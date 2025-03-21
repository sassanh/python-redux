"""Tests for `with_state` decorator."""

from __future__ import annotations

import inspect
import re
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


def test_name_attr(store: StoreType) -> None:
    """Test `with_state` decorator name attribute."""

    @store.with_state(lambda state: state.value)
    def decorated(value: int) -> int:
        return value

    assert decorated.__name__ == 'WithState:decorated'

    inline_decorated = store.with_state(lambda state: state.value)(
        lambda value: value,
    )

    assert inline_decorated.__name__ == 'WithState:<lambda>'

    class Decorated:
        def __call__(self, value: int) -> int:
            return value

        def __repr__(self) -> str:
            return 'Decorated'

    decorated_instance = store.with_state(lambda state: state.value)(Decorated())

    assert decorated_instance.__name__ == 'WithState:Decorated'

    store.dispatch(InitAction())
    store.dispatch(FinishAction())


def test_repr(store: StoreType) -> None:
    """Test `with_state` decorator `__repr__` method."""

    @store.with_state(lambda state: state.value)
    def func(value: int) -> int:
        return value

    assert re.match(
        r'.*\(func: <function test_repr\.<locals>\.func at .*>\)$',
        repr(func),
    )

    store.dispatch(InitAction())
    store.dispatch(FinishAction())


def test_signature(store: StoreType) -> None:
    """Test `with_state` decorator `__signature__` attribute."""

    @store.with_state(lambda state: state.value)
    def func(
        value: int,
        some_positional_parameter: str,
        some_positional_parameter_with_default: int = 0,
        *,
        some_keyword_parameter: bool,
        some_keyword_parameter_with_default: int = 1,
    ) -> int:
        _ = (
            some_positional_parameter,
            some_positional_parameter_with_default,
            some_keyword_parameter,
            some_keyword_parameter_with_default,
        )
        return value

    signature = inspect.signature(func)
    assert len(signature.parameters) == 4

    assert 'some_positional_parameter' in signature.parameters
    assert (
        signature.parameters['some_positional_parameter'].default
        is inspect.Parameter.empty
    )
    assert signature.parameters['some_positional_parameter'].annotation == 'str'

    assert 'some_positional_parameter_with_default' in signature.parameters
    assert signature.parameters['some_positional_parameter_with_default'].default == 0
    assert (
        signature.parameters['some_positional_parameter_with_default'].annotation
        == 'int'
    )

    assert 'some_keyword_parameter' in signature.parameters
    assert (
        signature.parameters['some_keyword_parameter'].default
        is inspect.Parameter.empty
    )
    assert signature.parameters['some_keyword_parameter'].annotation == 'bool'

    assert 'some_keyword_parameter_with_default' in signature.parameters
    assert signature.parameters['some_keyword_parameter_with_default'].default == 1
    assert (
        signature.parameters['some_keyword_parameter_with_default'].annotation == 'int'
    )

    assert 'value' not in signature.parameters

    assert signature.return_annotation == 'int'

    store.dispatch(InitAction())
    store.dispatch(FinishAction())


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
