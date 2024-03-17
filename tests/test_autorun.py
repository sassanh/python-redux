# ruff: noqa: D100, D101, D102, D103, D104, D107
from __future__ import annotations

import re
from dataclasses import replace
from typing import TYPE_CHECKING, Generator

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
    from redux.test import StoreSnapshotContext


class StateType(Immutable):
    value: int


class IncrementAction(BaseAction): ...


class IncrementByTwoAction(BaseAction): ...


Action = IncrementAction | IncrementByTwoAction | InitAction | FinishAction


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

    if isinstance(action, IncrementByTwoAction):
        return replace(state, value=state.value + 2)

    return state


@pytest.fixture()
def store() -> Generator[Store[StateType, Action, FinishEvent], None, None]:
    store = Store(reducer, options=CreateStoreOptions(auto_init=True))
    yield store
    store.dispatch(IncrementAction())
    store.dispatch(IncrementByTwoAction())
    store.dispatch(IncrementAction())
    store.dispatch(FinishAction())


def test_general(
    store_snapshot: StoreSnapshotContext,
    store: Store[StateType, Action, BaseEvent],
) -> None:
    store_snapshot.set_store(store)

    @store.autorun(lambda state: state.value)
    def _(value: int) -> int:
        store_snapshot.take()
        return value


def test_ignore_attribute_error_in_selector(
    store_snapshot: StoreSnapshotContext,
    store: Store[StateType, Action, BaseEvent],
) -> None:
    store_snapshot.set_store(store)

    @store.autorun(lambda state: state.non_existing)  # pyright: ignore[reportAttributeAccessIssue]
    def _(_: int) -> int:
        pytest.fail('This should never be called')


def test_ignore_attribute_error_in_comparator(
    store_snapshot: StoreSnapshotContext,
    store: Store[StateType, Action, BaseEvent],
) -> None:
    store_snapshot.set_store(store)

    @store.autorun(
        lambda state: state.value,
        lambda state: state.non_existing,  # pyright: ignore[reportAttributeAccessIssue]
    )
    def _(_: int) -> int:
        pytest.fail('This should never be called')


def test_with_old_value(
    store_snapshot: StoreSnapshotContext,
    store: Store[StateType, Action, BaseEvent],
) -> None:
    store_snapshot.set_store(store)

    @store.autorun(lambda state: state.value)
    def _(value: int, old_value: int | None) -> int:
        store_snapshot.take()
        return value - (old_value or 0)


def test_with_comparator(
    store_snapshot: StoreSnapshotContext,
    store: Store[StateType, Action, BaseEvent],
) -> None:
    store_snapshot.set_store(store)

    @store.autorun(
        lambda state: state.value,
        lambda state: state.value % 2,
    )
    def _(value: int) -> int:
        store_snapshot.take()
        return value


def test_with_comparator_and_old_value(
    store_snapshot: StoreSnapshotContext,
    store: Store[StateType, Action, BaseEvent],
) -> None:
    store_snapshot.set_store(store)

    @store.autorun(
        lambda state: state.value,
        lambda state: state.value % 2,
    )
    def _(value: int, old_value: int | None) -> int:
        store_snapshot.take()
        return value - (old_value or 0)


def test_value_property(
    store_snapshot: StoreSnapshotContext,
    store: Store[StateType, Action, BaseEvent],
) -> None:
    store_snapshot.set_store(store)

    @store.autorun(lambda state: state.value)
    def render(value: int) -> int:
        store_snapshot.take()
        return value

    def check(_: int) -> None:
        state = store._state  # noqa: SLF001
        if not state:
            return
        assert render.value == state.value

    render.subscribe(check)


def test_callability(
    store_snapshot: StoreSnapshotContext,
    store: Store[StateType, Action, BaseEvent],
) -> None:
    store_snapshot.set_store(store)

    @store.autorun(lambda state: state.value)
    def render(value: int) -> int:
        store_snapshot.take()
        return value

    def check(state: StateType) -> None:
        assert render() == state.value

    store.subscribe(check)


def test_subscription(
    store_snapshot: StoreSnapshotContext,
    store: Store[StateType, Action, BaseEvent],
) -> None:
    store_snapshot.set_store(store)

    @store.autorun(lambda state: state.value)
    def render(value: int) -> int:
        return value

    def reaction(_: int) -> None:
        store_snapshot.take()

    render.subscribe(reaction, initial_run=True)


def test_unsubscription(
    store_snapshot: StoreSnapshotContext,
    store: Store[StateType, Action, BaseEvent],
) -> None:
    store_snapshot.set_store(store)

    @store.autorun(lambda state: state.value)
    def render(value: int) -> int:
        return value

    def reaction(_: int) -> None:
        pytest.fail('This should never be called')

    unsubscribe = render.subscribe(reaction, initial_run=False)
    unsubscribe()


def test_repr(
    store_snapshot: StoreSnapshotContext,
    store: Store[StateType, Action, BaseEvent],
) -> None:
    store_snapshot.set_store(store)

    @store.autorun(lambda state: state.value)
    def render(value: int) -> int:
        return value

    assert re.match(
        r'.*\(func: <function test_repr\.<locals>\.render at .*>, last_value: 0\)$',
        repr(render),
    )

    store.dispatch(IncrementAction())

    assert re.match(
        r'.*\(func: <function test_repr\.<locals>\.render at .*>, last_value: 1\)$',
        repr(render),
    )
