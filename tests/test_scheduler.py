# ruff: noqa: D100, D101, D102, D103, D107
from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import replace
from typing import TYPE_CHECKING, TypeAlias
from unittest.mock import call

from immutable import Immutable

from redux.basic_types import (
    BaseAction,
    BaseEvent,
    CompleteReducerResult,
    FinishAction,
    FinishEvent,
    InitAction,
    InitializationActionError,
    ReducerResult,
    StoreOptions,
)
from redux.main import Store

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from pytest_mock import MockerFixture


class StateType(Immutable):
    value: int


class IncrementAction(BaseAction): ...


class WaitEvent(BaseEvent): ...


Action = IncrementAction | InitAction | FinishAction
Event = WaitEvent


def reducer(
    state: StateType | None,
    action: Action,
) -> ReducerResult[StateType, Action, Event]:
    if state is None:
        if isinstance(action, InitAction):
            return StateType(value=0)
        raise InitializationActionError(action)

    if isinstance(action, IncrementAction):
        return CompleteReducerResult(
            state=replace(state, value=state.value + 1),
            events=[WaitEvent()],
        )
    return state


StoreType: TypeAlias = Store[StateType, IncrementAction | InitAction, FinishEvent]


class Scheduler(threading.Thread):
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[tuple[Callable[[], None], float]]
    exception: Exception | None = None

    def __init__(self) -> None:
        super().__init__()
        self.stopped = False
        self._callbacks: list[tuple[Callable[[], None], float]] = []
        self.queue = asyncio.Queue()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def schedule_callback(
        self,
        callback: Callable[[], None],
        *,
        interval: bool,
    ) -> None:
        self.queue.put_nowait((callback, interval))

    def run(self) -> None:
        self.loop.run_until_complete(self._run())

    async def _run(self) -> None:
        try:
            while not self.stopped:
                try:
                    callback, interval = self.queue.get_nowait()
                    callback()
                    if interval:
                        await self.queue.put((callback, interval))
                except asyncio.QueueEmpty:
                    pass
                await asyncio.sleep(0.01)
        except Exception as exception:  # noqa: BLE001
            self.exception = exception

    async def graceful_stop(self) -> None:
        await asyncio.sleep(0.05)
        self.loop.stop()

    def schedule_stop(self) -> None:
        self.stopped = True
        self.loop.call_soon_threadsafe(self.loop.create_task, self.graceful_stop())


def test_scheduler(mocker: MockerFixture) -> None:
    scheduler = Scheduler()
    scheduler.start()

    def _create_task_with_callback(
        coro: Coroutine,
        callback: Callable[[asyncio.Task], None] | None = None,
    ) -> None:
        def create_task_with_callback() -> None:
            task = scheduler.loop.create_task(coro)
            if callback:
                callback(task)

        scheduler.loop.call_soon_threadsafe(create_task_with_callback)

    store = Store(
        reducer,
        options=StoreOptions(
            auto_init=True,
            scheduler=scheduler.schedule_callback,
            task_creator=_create_task_with_callback,
            on_finish=scheduler.schedule_stop,
            grace_time_in_seconds=0.2,
        ),
    )

    render = mocker.stub()

    store.subscribe_event(
        FinishEvent,
        lambda _: time.sleep(0.1) or store.dispatch(IncrementAction()),
    )

    store._subscribe(render)  # noqa: SLF001

    time.sleep(0.1)

    for _ in range(10):
        store.dispatch(IncrementAction())
    store.dispatch(FinishAction())

    scheduler.join()

    if scheduler.exception is not None:
        raise scheduler.exception

    render.assert_has_calls(
        [call(StateType(value=i)) for i in range(11)] + [call(StateType(value=10))],
    )
