# ruff: noqa: D100, D101, D102, D103, D104, D107
from __future__ import annotations

import re
from dataclasses import replace
from typing import TYPE_CHECKING, Any, Generator, cast
from unittest.mock import call

import pytest
from immutable import Immutable

from redux.basic_types import (
    AutorunOptions,
    BaseAction,
    CompleteReducerResult,
    CreateStoreOptions,
    FinishAction,
    FinishEvent,
    InitAction,
    InitializationActionError,
)
from redux.main import Store

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from redux_pytest.fixtures import StoreSnapshot


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
    store = Store(reducer, options=CreateStoreOptions(auto_init=True))
    yield store

    store.dispatch(IncrementAction())
    store.dispatch(IncrementByTwoAction())
    store.dispatch(IncrementAction())
    store.dispatch(FinishAction())


def test_general(store_snapshot: StoreSnapshot, store: StoreType) -> None:
    @store.autorun(lambda state: state.value)
    def _(value: int) -> int:
        store_snapshot.take()
        return value


def test_ignore_attribute_error_in_selector(store: StoreType) -> None:
    @store.autorun(lambda state: cast(Any, state).non_existing)
    def _(_: int) -> int:
        pytest.fail('This should never be called')


def test_ignore_attribute_error_in_comparator(store: StoreType) -> None:
    @store.autorun(
        lambda state: state.value,
        lambda state: cast(Any, state).non_existing,
    )
    def _(_: int) -> int:
        pytest.fail('This should never be called')


def test_with_comparator(
    store_snapshot: StoreSnapshot,
    store: StoreType,
) -> None:
    @store.autorun(
        lambda state: state.value,
        lambda state: state.value % 2,
    )
    def _(value: int) -> int:
        store_snapshot.take()
        return value


def test_value_property(store_snapshot: StoreSnapshot, store: StoreType) -> None:
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


def test_callability(store_snapshot: StoreSnapshot, store: StoreType) -> None:
    @store.autorun(lambda state: state.value)
    def render(value: int) -> int:
        store_snapshot.take()
        return value

    def check(state: StateType) -> None:
        assert render() == state.value

    store.subscribe(check)


def test_subscription(store_snapshot: StoreSnapshot, store: StoreType) -> None:
    @store.autorun(lambda state: state.value)
    def render(value: int) -> int:
        return value

    def reaction(_: int) -> None:
        store_snapshot.take()

    render.subscribe(reaction, initial_run=True)


def test_unsubscription(store: StoreType) -> None:
    @store.autorun(lambda state: state.value)
    def render(value: int) -> int:
        return value

    def reaction(_: int) -> None:
        pytest.fail('This should never be called')

    unsubscribe = render.subscribe(reaction, initial_run=False)
    unsubscribe()


def test_repr(store: StoreType) -> None:
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


def test_auto_call_without_reactive(store: StoreType) -> None:
    with pytest.raises(
        ValueError,
        match='^`reactive` must be `True` if `auto_call` is `True`$',
    ):

        @store.autorun(
            lambda state: state.value,
            options=AutorunOptions(reactive=False, auto_call=True),
        )
        def _(_: int) -> int:
            pytest.fail('This should never be called')


call_sequence = [
    # 0
    [
        (IncrementAction()),
    ],
    # 1
    [
        (IncrementAction()),
        (DecrementAction()),
        (IncrementByTwoAction()),
        (DecrementAction()),
        (IncrementAction()),
    ],
    # 3
    [
        (DecrementAction()),
        (DecrementAction()),
    ],
    # 1
]


def test_no_auto_call_with_initial_call_and_reactive_set(
    store: StoreType,
    mocker: MockerFixture,
) -> None:
    def render(_: int) -> None: ...

    render = mocker.create_autospec(render)

    render_autorun = store.autorun(
        lambda state: state.value,
        options=AutorunOptions(reactive=True, auto_call=False, initial_call=True),
    )(render)

    for actions in call_sequence:
        for action in actions:
            store.dispatch(action)
        render_autorun()

    assert render.mock_calls == [call(0), call(1), call(3), call(1)]


def test_no_auto_call_and_no_initial_call_with_reactive_set(
    store: StoreType,
    mocker: MockerFixture,
) -> None:
    def render(_: int) -> None: ...

    render = mocker.create_autospec(render)

    render_autorun = store.autorun(
        lambda state: state.value,
        options=AutorunOptions(reactive=True, auto_call=False, initial_call=False),
    )(render)

    for actions in call_sequence:
        for action in actions:
            store.dispatch(action)
        render_autorun()

    assert render.mock_calls == [call(1), call(3), call(1)]


def test_with_auto_call_and_initial_call_and_reactive_set(
    store: StoreType,
    mocker: MockerFixture,
) -> None:
    def render(_: int) -> None: ...

    render = mocker.create_autospec(render)

    render_autorun = store.autorun(
        lambda state: state.value,
        options=AutorunOptions(reactive=True, auto_call=True, initial_call=True),
    )(render)

    for actions in call_sequence:
        for action in actions:
            store.dispatch(action)
        render_autorun()

    assert render.mock_calls == [
        call(0),
        call(1),
        call(2),
        call(1),
        call(3),
        call(2),
        call(3),
        call(2),
        call(1),
    ]


def test_view_mode_with_arguments_autorun(
    store: StoreType,
) -> None:
    @store.autorun(
        lambda state: state.value,
        options=AutorunOptions(
            reactive=False,
            auto_call=False,
            initial_call=False,
            default_value=0,
        ),
    )
    def render(_: int, *, some_other_value: int) -> int:
        return some_other_value

    assert render(some_other_value=12345) == 12345
