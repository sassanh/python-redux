# ruff: noqa: D100, D101, D102, D103, D104, D107
from __future__ import annotations

from immutable import Immutable

from redux.basic_types import (
    BaseAction,
    CreateStoreOptions,
    FinishAction,
    FinishEvent,
)
from redux.main import Store


class StateType(Immutable):
    value: int


StoreType = Store[StateType, BaseAction, FinishEvent]


def test_snapshot() -> None:
    initial_state = StateType(value=0)

    store = Store(
        lambda state, __: state or initial_state,
        options=CreateStoreOptions(auto_init=True),
    )

    assert store.snapshot == {'value': 0}

    store.dispatch(FinishAction())
