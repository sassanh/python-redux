# ruff: noqa: D100, D101, D102, D103, D104, D107

from __future__ import annotations

from dataclasses import replace

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


class StateType(Immutable):
    value: int


class IncrementAction(BaseAction): ...


class DecrementAction(BaseAction): ...


class SomeEvent(BaseEvent): ...


Action = IncrementAction | DecrementAction | InitAction | FinishAction


def reducer(
    state: StateType | None,
    action: Action,
) -> StateType | CompleteReducerResult[StateType, Action, SomeEvent | FinishEvent]:
    if state is None:
        if isinstance(action, InitAction):
            return StateType(value=0)
        raise InitializationActionError(action)

    if isinstance(action, IncrementAction):
        return replace(state, value=state.value + 1)

    if isinstance(action, DecrementAction):
        return replace(state, value=state.value - 1)

    return state


class StoreType(Store[StateType, Action, FinishEvent | SomeEvent]):
    @property
    def state(self: StoreType) -> StateType | None:
        return self._state


@pytest.fixture()
def store() -> StoreType:
    return StoreType(reducer, options=CreateStoreOptions(auto_init=True))


def test_identity_action_middleware(store: StoreType) -> None:
    calls = []

    def middleware(action: Action) -> Action:
        calls.append(action)
        if isinstance(action, IncrementAction):
            return DecrementAction()
        return action

    store.register_action_middleware(middleware)

    actions = [
        IncrementAction(),
        IncrementAction(),
        FinishAction(),
    ]

    def check() -> None:
        assert calls == actions
        assert store.state
        assert store.state.value == -2

    store.subscribe_event(FinishEvent, check)

    for action in actions:
        store.dispatch(action)


def test_cancelling_action_middleware(store: StoreType) -> None:
    calls = []

    def middleware(action: Action) -> Action | None:
        calls.append(action)
        if len(calls) == 1:
            return None
        return action

    store.register_action_middleware(middleware)

    actions = [
        IncrementAction(),
        IncrementAction(),
        FinishAction(),
    ]

    def check() -> None:
        assert store.state
        assert store.state.value == 1

    store.subscribe_event(FinishEvent, check)

    for action in actions:
        store.dispatch(action)


def test_identity_event_middlewares(store: StoreType) -> None:
    calls = []

    def middleware(event: SomeEvent) -> SomeEvent | FinishEvent:
        calls.append(event)
        if len(calls) == 2:
            return FinishEvent()
        return event

    store.register_event_middleware(middleware)

    events = [
        SomeEvent(),
        SomeEvent(),
        SomeEvent(),
    ]

    def check() -> None:
        assert calls == events

    store.subscribe_event(FinishEvent, check)

    for event in events:
        store.dispatch(event)


def test_cancelling_event_middlewares(store: StoreType) -> None:
    calls = []

    def middleware(event: SomeEvent | FinishEvent) -> SomeEvent | FinishEvent | None:
        calls.append(event)
        if len(calls) == 1 and isinstance(event, SomeEvent):
            return None
        return event

    side_effect_calls = []

    def some_side_effect(event: SomeEvent) -> None:
        side_effect_calls.append(event)

    store.register_event_middleware(middleware)

    events = [
        SomeEvent(),
        SomeEvent(),
    ]

    def check() -> None:
        assert side_effect_calls == events[1:2]

    store.subscribe_event(SomeEvent, some_side_effect)
    store.subscribe_event(FinishEvent, check)

    for event in events:
        store.dispatch(event)
    store.dispatch(FinishAction())
