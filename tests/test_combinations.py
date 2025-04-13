# ruff: noqa: D100, D101, D102, D103, D104, D107
from __future__ import annotations

from dataclasses import replace
from typing import Literal

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


class StateType(Immutable):
    value1: int
    value2: int


class IncrementAction(BaseAction):
    which: Literal[1, 2]


Action = IncrementAction | InitAction | FinishAction


def reducer(
    state: StateType | None,
    action: Action,
) -> StateType | CompleteReducerResult[StateType, Action, FinishEvent]:
    if state is None:
        if isinstance(action, InitAction):
            return StateType(value1=0, value2=0)
        raise InitializationActionError(action)

    if isinstance(action, IncrementAction):
        field_name = f'value{action.which}'
        return replace(
            state,
            **{field_name: getattr(state, field_name) + 1},
        )

    return state


StoreType = Store[StateType, Action, FinishEvent]


@pytest.fixture
def store() -> StoreType:
    return Store(reducer, options=StoreOptions(auto_init=True))


def test_autorun_of_view(store: StoreType) -> None:
    @store.autorun(
        lambda state: state.value2,
        lambda state: (state.value1, state.value2),
    )
    @store.view(lambda state: state.value1)
    def view(value1: int, value2: int) -> tuple[int, int]:
        return (value1, value2)

    assert view() == (0, 0)

    store.dispatch(IncrementAction(which=1))

    assert view() == (1, 0)

    store.dispatch(IncrementAction(which=2))

    assert view() == (1, 1)

    store.dispatch(FinishAction())
