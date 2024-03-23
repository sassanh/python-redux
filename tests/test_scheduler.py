# ruff: noqa: D100, D101, D102, D103, D104, D107, T201
from __future__ import annotations

import asyncio
import threading
from dataclasses import replace
from typing import TYPE_CHECKING, Callable, TypeAlias
from unittest.mock import call

from immutable import Immutable

from redux.basic_types import (
    BaseAction,
    CreateStoreOptions,
    FinishAction,
    FinishEvent,
    InitAction,
    InitializationActionError,
)
from redux.main import Store

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


class StateType(Immutable):
    value: int


class IncrementAction(BaseAction): ...


def reducer(state: StateType | None, action: IncrementAction | InitAction) -> StateType:
    if state is None:
        if isinstance(action, InitAction):
            return StateType(value=0)
        raise InitializationActionError(action)

    if isinstance(action, IncrementAction):
        return replace(state, value=state.value + 1)
    return state


StoreType: TypeAlias = Store[StateType, IncrementAction | InitAction, FinishEvent]


class Scheduler(threading.Thread):
    def __init__(self: Scheduler) -> None:
        super().__init__()
        self.stopped = False
        self._callbacks: list[tuple[Callable[[], None], float]] = []
        self.loop = asyncio.new_event_loop()
        self.tasks: set[asyncio.Task] = set()

    def run(self: Scheduler) -> None:
        self.loop.run_forever()

    def set(self: Scheduler, callback: Callable[[], None], *, interval: bool) -> None:
        self.loop.call_soon_threadsafe(
            self.loop.create_task,
            self.call_callback(callback, interval=interval),
        )

    async def call_callback(
        self: Scheduler,
        callback: Callable[[], None],
        *,
        interval: bool,
    ) -> None:
        if self.stopped:
            return
        self.tasks.add(self.loop.create_task(asyncio.to_thread(callback)))
        await asyncio.sleep(0.01)
        if interval:
            self.tasks.add(
                self.loop.create_task(self.call_callback(callback, interval=interval)),
            )

    async def graceful_stop(self: Scheduler) -> None:
        await asyncio.sleep(0.05)
        self.loop.stop()

    def schedule_stop(self: Scheduler) -> None:
        self.stopped = True
        self.loop.call_soon_threadsafe(self.loop.create_task, self.graceful_stop())


def test_scheduler(
    mocker: MockerFixture,
) -> None:
    scheduler = Scheduler()
    scheduler.start()

    store = Store(
        reducer,
        options=CreateStoreOptions(
            auto_init=True,
            scheduler=scheduler.set,
            on_finish=scheduler.schedule_stop,
        ),
    )

    render = mocker.stub()

    store.subscribe(render)
    import time

    time.sleep(0.1)

    for _ in range(10):
        store.dispatch(IncrementAction())
    store.dispatch(FinishAction())

    scheduler.join()

    render.assert_has_calls(
        [
            call(StateType(value=0)),
            call(StateType(value=10)),
        ],
    )
