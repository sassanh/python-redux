# ruff: noqa: D100, D101, D102, D103, D104, D107
from __future__ import annotations

import asyncio
import threading
from dataclasses import replace
from typing import Callable, Coroutine, Generator

import pytest
from immutable import Immutable

from redux.basic_types import (
    BaseAction,
    CompleteReducerResult,
    CreateStoreOptions,
    EventSubscriptionOptions,
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


class LoopThread(threading.Thread):
    def __init__(self: LoopThread) -> None:
        super().__init__()
        self.loop = asyncio.new_event_loop()

    def run(self: LoopThread) -> None:
        self.loop.run_forever()

    def stop(self: LoopThread) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)


@pytest.fixture()
def loop() -> LoopThread:
    loop_thread = LoopThread()
    loop_thread.start()
    return loop_thread


Action = IncrementAction | SetMirroredValueAction | InitAction | FinishAction
StoreType = Store[StateType, Action, FinishEvent]


@pytest.fixture()
def store(
    loop: LoopThread,
) -> Generator[StoreType, None, None]:
    def _create_task_with_callback(
        coro: Coroutine,
        callback: Callable[[asyncio.Task], None] | None = None,
    ) -> None:
        def create_task_with_callback() -> None:
            task = loop.loop.create_task(coro)
            if callback:
                callback(task)

        loop.loop.call_soon_threadsafe(create_task_with_callback)

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


def test_create_task(
    store: StoreType,
    loop: LoopThread,
) -> None:
    async def task(value: int) -> int:
        await asyncio.sleep(0.5)
        return value

    def done(task: asyncio.Task) -> None:
        assert task.result() == 1
        store.dispatch(FinishAction())

    def callback(task: asyncio.Task) -> None:
        task.add_done_callback(done)

    store._create_task(task(1), callback=callback)  # noqa: SLF001

    def finish() -> None:
        loop.stop()

    store.subscribe_event(FinishEvent, finish)


def test_autorun(
    store: StoreType,
    loop: LoopThread,
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
        store.dispatch(FinishAction())

    async def finish() -> None:
        loop.stop()

    store.subscribe_event(FinishEvent, finish)
    store.subscribe_event(FinishEvent, finish)


def test_subscription(
    store: StoreType,
    loop: LoopThread,
) -> None:
    async def render(state: StateType) -> None:
        if state.value == INCREMENTS:
            unsubscribe()
            store.dispatch(FinishAction())
            loop.stop()

    unsubscribe = store.subscribe(render)


def test_event_subscription(
    store: StoreType,
    loop: LoopThread,
) -> None:
    async def finish() -> None:
        await asyncio.sleep(0.1)
        loop.stop()

    store.subscribe_event(FinishEvent, finish)
    store.dispatch(FinishAction())


def test_immediate_event_subscription(
    store: StoreType,
    loop: LoopThread,
) -> None:
    async def finish() -> None:
        await asyncio.sleep(0.1)
        loop.stop()

    store.subscribe_event(
        FinishEvent,
        finish,
        options=EventSubscriptionOptions(immediate_run=True),
    )
    store.dispatch(FinishAction())
