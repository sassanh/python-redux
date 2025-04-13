# ruff: noqa: D100, D101, D102, D103, D104, D107
from __future__ import annotations

import inspect
import re
from dataclasses import replace
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import call

import pytest
from immutable import Immutable

from redux.basic_types import (
    AutorunOptions,
    BaseAction,
    FinishAction,
    FinishEvent,
    InitAction,
    InitializationActionError,
    ReducerResult,
    StoreOptions,
)
from redux.main import Store

if TYPE_CHECKING:
    from collections.abc import Generator

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
) -> ReducerResult[StateType, Action, FinishEvent]:
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
    store = Store(reducer, options=StoreOptions(auto_init=True))
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


def test_name_attr(store: StoreType) -> None:
    """Test `autorun` decorator name attribute."""

    @store.autorun(lambda state: state.value)
    def decorated(value: int) -> int:
        return value

    assert decorated.__name__ == 'Autorun:decorated'
    assert decorated.__qualname__ == 'Autorun:test_name_attr.<locals>.decorated'

    inline_decorated = store.autorun(lambda state: state.value)(
        lambda value: value,
    )

    assert inline_decorated.__name__ == 'Autorun:<lambda>'

    class Decorated:
        def __call__(self, value: int) -> int:
            return value

        def __repr__(self) -> str:
            return 'Decorated'

    decorated_instance = store.autorun(lambda state: state.value)(Decorated())

    assert decorated_instance.__name__ == 'Autorun:Decorated'


def test_signature(store: StoreType) -> None:
    """Test `with_state` decorator `__signature__` attribute."""

    @store.autorun(
        lambda state: state.value,
        options=AutorunOptions(
            initial_call=False,
            reactive=False,
        ),
    )
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


def test_ignore_attribute_error_in_selector(store: StoreType) -> None:
    @store.autorun(lambda state: cast('Any', state).non_existing)
    def _(_: int) -> None:
        pytest.fail('This should never be called')


def test_ignore_attribute_error_in_comparator(store: StoreType) -> None:
    @store.autorun(
        lambda state: state.value,
        lambda state: cast('Any', state).non_existing,
    )
    def _(_: int) -> None:
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

    store._subscribe(check)  # noqa: SLF001


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
        options=AutorunOptions(reactive=False, initial_call=True),
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
        options=AutorunOptions(reactive=False, initial_call=False),
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

    trigger_autorun = store.autorun(
        lambda state: state.value,
        options=AutorunOptions(reactive=True, initial_call=True),
    )(render)

    for actions in call_sequence:
        for action in actions:
            store.dispatch(action)
        trigger_autorun()

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


def test_task_mode_without_arguments(
    store: StoreType,
) -> None:
    @store.autorun(
        lambda state: state.value,
        options=AutorunOptions(
            reactive=False,
            initial_call=False,
            memoization=False,
        ),
    )
    def act(value: int) -> int:
        assert value == 4, (
            'This is expected to be called only after the last action is dispatched'
        )
        return value

    def check() -> None:
        assert act() == 4

    store.subscribe_event(FinishEvent, check)


def test_view_mode_with_arguments_autorun(
    store: StoreType,
) -> None:
    @store.autorun(
        lambda state: state.value,
        options=AutorunOptions(
            reactive=False,
            initial_call=False,
            memoization=True,
            default_value=0,
        ),
    )
    def render(_: int, *, some_other_value: int) -> int:
        return some_other_value

    assert render(some_other_value=12345) == 12345
