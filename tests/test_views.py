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
    ViewOptions,
)
from redux.main import Store

if TYPE_CHECKING:
    from collections.abc import Generator


class StateType(Immutable):
    value: int


class IncrementAction(BaseAction): ...


class DecrementAction(BaseAction): ...


class IncrementByTwoAction(BaseAction): ...


Action = (
    IncrementAction | DecrementAction | IncrementByTwoAction | InitAction | FinishAction
)


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

    if isinstance(action, DecrementAction):
        return replace(state, value=state.value - 1)

    if isinstance(action, IncrementByTwoAction):
        return replace(state, value=state.value + 2)

    return state


StoreType = Store[StateType, Action, FinishEvent]


@pytest.fixture
def store() -> Generator[StoreType, None, None]:
    store: StoreType = Store(reducer, options=StoreOptions(auto_init=True))
    yield store

    store.dispatch(IncrementAction())
    store.dispatch(IncrementByTwoAction())
    store.dispatch(IncrementAction())
    store.dispatch(FinishAction())


def test_general(
    store: StoreType,
) -> None:
    @store.view(lambda state: state.value)
    def render(value: int) -> int:
        return value

    store.dispatch(IncrementAction())

    assert render() == 1


def test_not_reactive(
    store: StoreType,
) -> None:
    runs = 0

    @store.view(lambda state: state.value)
    def render(value: int) -> int:
        nonlocal runs
        runs += 1
        return value

    store.dispatch(IncrementAction())
    store.dispatch(IncrementAction())
    store.dispatch(IncrementAction())

    assert render() == 3
    assert runs == 1


def test_uninitialized_store(
    store: StoreType,
) -> None:
    store = Store(reducer, options=StoreOptions(auto_init=False))

    @store.view(lambda state: state.value)
    def render(value: int) -> int:
        return value

    assert render() is None

    store.dispatch(InitAction())
    assert render() == 0

    store.dispatch(IncrementAction())
    assert render() == 1

    store.dispatch(FinishAction())


def test_with_default_value_and_uninitialized_store(
    store: StoreType,
) -> None:
    store = Store(reducer, options=StoreOptions(auto_init=False))

    @store.view(lambda state: state.value, options=ViewOptions(default_value=5))
    def render(value: int) -> int:
        return value

    assert render() == 5

    store.dispatch(InitAction())
    assert render() == 0

    store.dispatch(IncrementAction())
    assert render() == 1

    store.dispatch(FinishAction())


def test_with_arguments(
    store: StoreType,
) -> None:
    @store.view(lambda state: state.value)
    def render(_: int, *, some_other_value: int) -> int:
        return some_other_value

    store.dispatch(IncrementAction())

    assert render(some_other_value=12345) == 12345


def test_methods(store: StoreType) -> None:
    class SomeClass:
        @store.view(lambda state: state.value)
        def render(self, value: int) -> int:
            return value

    instance = SomeClass()

    assert instance.render() == 0

    store.dispatch(IncrementAction())

    assert instance.render() == 1
