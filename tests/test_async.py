# ruff: noqa: D100, D101, D102, D103, D104, D107
from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import TYPE_CHECKING

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
    ViewOptions,
)
from redux.main import Store

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from redux_pytest.fixtures.event_loop import LoopThread

INCREMENTS = 20


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


@pytest.fixture
def store(event_loop: LoopThread) -> StoreType:
    def _create_task_with_callback(
        coro: Coroutine,
        callback: Callable[[asyncio.Task], None] | None = None,
    ) -> None:
        def create_task_with_callback() -> None:
            task = event_loop.loop.create_task(coro)
            if callback:
                callback(task)

        event_loop.loop.call_soon_threadsafe(create_task_with_callback)

    return Store(
        reducer,
        options=CreateStoreOptions(
            auto_init=True,
            task_creator=_create_task_with_callback,
        ),
    )


def dispatch_actions(store: StoreType) -> None:
    for _ in range(INCREMENTS):
        store.dispatch(IncrementAction())


def test_autorun(
    store: StoreType,
    event_loop: LoopThread,
) -> None:
    @store.autorun(lambda state: state.value)
    async def sync_mirror(value: int) -> int:
        await asyncio.sleep(value / 10)
        store.dispatch(SetMirroredValueAction(value=value))
        return value

    assert asyncio.iscoroutinefunction(sync_mirror)

    @store.autorun(
        lambda state: state.mirrored_value,
        lambda state: state.mirrored_value >= INCREMENTS,
    )
    def _(mirrored_value: int) -> None:
        if mirrored_value < INCREMENTS:
            return
        event_loop.stop()
        store.dispatch(FinishAction())

    dispatch_actions(store)


def test_autorun_autoawait(
    store: StoreType,
    event_loop: LoopThread,
) -> None:
    @store.autorun(lambda state: state.value, options=AutorunOptions(auto_await=False))
    async def sync_mirror(value: int) -> int:
        store.dispatch(SetMirroredValueAction(value=value))
        return value * 2

    assert asyncio.iscoroutinefunction(sync_mirror)

    @store.autorun(lambda state: (state.value, state.mirrored_value))
    async def _(values: tuple[int, int]) -> None:
        value, mirrored_value = values
        if mirrored_value != value:
            assert 'awaited=False' in str(sync_mirror())
            await sync_mirror()
            assert 'awaited=True' in str(sync_mirror())
            with pytest.raises(
                RuntimeError,
                match=r'^cannot reuse already awaited coroutine$',
            ):
                await sync_mirror()
        elif value < INCREMENTS:
            store.dispatch(IncrementAction())
        else:
            event_loop.stop()
            store.dispatch(FinishAction())


def test_autorun_default_value(
    store: StoreType,
    event_loop: LoopThread,
) -> None:
    @store.autorun(lambda state: state.value, options=AutorunOptions(default_value=5))
    async def _(value: int) -> int:
        store.dispatch(SetMirroredValueAction(value=value))
        return value

    @store.autorun(
        lambda state: state.mirrored_value,
        lambda state: state.mirrored_value >= INCREMENTS,
    )
    def _(mirrored_value: int) -> None:
        if mirrored_value < INCREMENTS:
            return
        event_loop.stop()
        store.dispatch(FinishAction())

    dispatch_actions(store)


def test_view(
    store: StoreType,
    event_loop: LoopThread,
) -> None:
    calls = []

    @store.view(lambda state: state.value)
    async def doubled(value: int) -> int:
        calls.append(value)
        return value * 2

    @store.autorun(lambda state: state.value)
    async def _(value: int) -> None:
        assert await doubled() == value * 2
        for _ in range(10):
            await doubled()
        if value < INCREMENTS:
            store.dispatch(IncrementAction())
        else:
            event_loop.stop()
            store.dispatch(FinishAction())
            assert calls == list(range(INCREMENTS + 1))


def test_view_await(store: StoreType, event_loop: LoopThread) -> None:
    calls = []

    @store.view(lambda state: state.value)
    async def doubled(value: int) -> int:
        calls.append(value)
        return value * 2

    assert asyncio.iscoroutinefunction(doubled)

    @store.autorun(lambda state: state.value)
    async def _(value: int) -> None:
        calls_length = len(calls)
        assert await doubled() == value * 2
        assert len(calls) == calls_length + 1

        if value < INCREMENTS:
            store.dispatch(IncrementAction())
        else:
            event_loop.stop()
            store.dispatch(FinishAction())
            assert calls == list(range(INCREMENTS + 1))


def test_view_with_args(
    store: StoreType,
    event_loop: LoopThread,
) -> None:
    calls = []

    @store.view(lambda state: state.value)
    async def multiplied(value: int, factor: int) -> int:
        calls.append(value)
        return value * factor

    @store.autorun(lambda state: state.value)
    async def _(value: int) -> None:
        assert await multiplied(factor=2) == value * 2
        assert await multiplied(factor=3) == value * 3
        if value < INCREMENTS:
            store.dispatch(IncrementAction())
        else:
            event_loop.stop()
            store.dispatch(FinishAction())
            assert calls == [j for i in list(range(INCREMENTS + 1)) for j in [i] * 2]


def test_view_with_default_value(
    store: StoreType,
    event_loop: LoopThread,
) -> None:
    calls = []

    @store.view(lambda state: state.value, options=ViewOptions(default_value=5))
    async def doubled(value: int) -> int:
        calls.append(value)
        return value * 2

    @store.autorun(lambda state: state.value)
    async def _(value: int) -> None:
        assert await doubled() == value * 2
        if value < INCREMENTS:
            store.dispatch(IncrementAction())
        else:
            event_loop.stop()
            store.dispatch(FinishAction())
            assert calls == list(range(INCREMENTS + 1))

    store.dispatch(InitAction())


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

    dispatch_actions(store)


def test_event_subscription(
    store: StoreType,
    event_loop: LoopThread,
) -> None:
    async def finish() -> None:
        await asyncio.sleep(0.1)
        event_loop.stop()

    store.subscribe_event(FinishEvent, finish)
    store.dispatch(FinishAction())

    dispatch_actions(store)


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
