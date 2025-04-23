"""Test the custom autorun."""

from __future__ import annotations

from typing import cast

from immutable import Immutable
from typing_extensions import override

from redux.autorun import Autorun
from redux.basic_types import (
    BaseAction,
    BaseEvent,
    FinishAction,
    InitAction,
    InitializationActionError,
    StoreOptions,
)
from redux.main import Store


def test_custom_autorun() -> None:
    """Test the custom autorun."""

    class State(Immutable):
        value: int

    class _CounterAutorun[**Args](Autorun):
        counter = 0

        @override
        def call(
            self: _CounterAutorun[Args],
            *args: Args.args,
            **kwargs: Args.kwargs,
        ) -> None:
            _ = args, kwargs
            self.counter += 1

    def reducer(state: State | None, action: BaseAction) -> State:
        if state is None:
            if isinstance(action, InitAction):
                return State(value=0)
            raise InitializationActionError(action)

        return state

    store: Store[State, BaseAction, BaseEvent] = Store(
        reducer,
        options=StoreOptions(autorun_class=_CounterAutorun),
    )

    store.dispatch(InitAction())

    @store.autorun(lambda state: state.value)
    def autorun(value: int) -> int:
        return value

    assert cast('_CounterAutorun', autorun).counter == 1

    store.dispatch(BaseAction())
    store.dispatch(FinishAction())
