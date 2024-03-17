# ruff: noqa: D100, D101, D102, D103, D104, D107
from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Generator

import pytest
from immutable import Immutable

from redux.basic_types import (
    BaseAction,
    CompleteReducerResult,
    CreateStoreOptions,
    FinishAction,
    FinishEvent,
    InitAction,
    InitializationActionError,
)
from redux.main import Store

INCREMENTS = 2


class StateType(Immutable):
    value: int
    mirrored_value: int


class IncrementAction(BaseAction): ...


class SetMirroredValueAction(BaseAction):
    value: int


def reducer(
    state: StateType | None,
    action: Action,
) -> StateType | CompleteReducerResult[StateType, Action, FinishEvent]:
    if state is None:
        if isinstance(action, InitAction):
            return StateType(value=0, mirrored_value=0)
        raise InitializationActionError(action)

    if isinstance(action, IncrementAction):
        return replace(state, value=state.value + 1)
    if isinstance(action, SetMirroredValueAction):
        return replace(state, mirrored_value=action.value)
    return state


@pytest.fixture()
def loop() -> asyncio.AbstractEventLoop:
    return asyncio.get_event_loop()


Action = IncrementAction | SetMirroredValueAction | InitAction | FinishAction


@pytest.fixture()
def store(
    loop: asyncio.AbstractEventLoop,
) -> Generator[Store[StateType, Action, FinishEvent], None, None]:
    store = Store(
        reducer,
        options=CreateStoreOptions(auto_init=True, async_loop=loop),
    )
    yield store
    for _i in range(INCREMENTS):
        store.dispatch(IncrementAction())
    store.dispatch(FinishAction())
    loop.run_forever()


def test_autorun(
    store: Store[StateType, Action, FinishEvent],
    loop: asyncio.AbstractEventLoop,
) -> None:
    @store.autorun(lambda state: state.value)
    async def _(value: int) -> int:
        await asyncio.sleep(value / 10)
        store.dispatch(SetMirroredValueAction(value=value))
        return value

    @store.autorun(
        lambda state: state.mirrored_value,
        lambda state: state.mirrored_value >= INCREMENTS,
    )
    async def _(mirrored_value: int) -> None:
        if mirrored_value < INCREMENTS:
            return
        loop.call_soon_threadsafe(loop.stop)


def test_subscription(
    store: Store[StateType, Action, FinishEvent],
    loop: asyncio.AbstractEventLoop,
) -> None:
    async def render(state: StateType) -> None:
        await asyncio.sleep(0.1)
        if state.value == INCREMENTS:
            loop.call_soon_threadsafe(loop.stop)

    store.subscribe(render)


def test_event_subscription(
    store: Store[StateType, Action, FinishEvent],
    loop: asyncio.AbstractEventLoop,
) -> None:
    async def finish() -> None:
        await asyncio.sleep(0.1)
        loop.call_soon_threadsafe(loop.stop)

    store.subscribe_event(FinishEvent, finish)
