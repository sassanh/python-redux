# ruff: noqa: D100, D101, D102, D103, D104, D107
from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import TYPE_CHECKING, Callable, Coroutine, Generator

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

if TYPE_CHECKING:
    from redux_pytest.fixtures.event_loop import LoopThread

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


Action = IncrementAction | SetMirroredValueAction | InitAction | FinishAction
StoreType = Store[StateType, Action, FinishEvent]


@pytest.fixture()
def store(event_loop: LoopThread) -> Generator[StoreType, None, None]:
    def _create_task_with_callback(
        coro: Coroutine,
        callback: Callable[[asyncio.Task], None] | None = None,
    ) -> None:
        def create_task_with_callback() -> None:
            task = event_loop.loop.create_task(coro)
            if callback:
                callback(task)

        event_loop.loop.call_soon_threadsafe(create_task_with_callback)

    store = Store(
        reducer,
        options=CreateStoreOptions(
            auto_init=True,
            task_creator=_create_task_with_callback,
        ),
    )
    yield store
    for i in range(INCREMENTS):
        _ = i
        store.dispatch(IncrementAction())


def test_autorun(
    store: StoreType,
    event_loop: LoopThread,
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
        event_loop.stop()
        store.dispatch(FinishAction())


def test_subscription(
    store: StoreType,
    event_loop: LoopThread,
) -> None:
    async def render(state: StateType) -> None:
        if state.value == INCREMENTS:
            unsubscribe()
            store.dispatch(FinishAction())
            event_loop.stop()

    unsubscribe = store.subscribe(render)


def test_event_subscription(
    store: StoreType,
    event_loop: LoopThread,
) -> None:
    async def finish() -> None:
        await asyncio.sleep(0.1)
        event_loop.stop()

    store.subscribe_event(FinishEvent, finish)
    store.dispatch(FinishAction())


def test_event_subscription_with_no_task_creator(event_loop: LoopThread) -> None:
    store = Store(
        reducer,
        options=CreateStoreOptions(auto_init=True),
    )

    async def finish() -> None:
        await asyncio.sleep(0.1)
        event_loop.stop()

    store.subscribe_event(FinishEvent, finish)
    store.dispatch(FinishAction())
