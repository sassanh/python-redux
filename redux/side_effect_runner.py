"""Redux store for managing state and side effects."""

from __future__ import annotations

import asyncio
import contextlib
import threading
import weakref
from asyncio import Task, iscoroutine
from inspect import signature
from typing import TYPE_CHECKING, Any, Callable, Generic, cast

from redux.basic_types import Event, EventHandler

if TYPE_CHECKING:
    import queue


class SideEffectRunnerThread(threading.Thread, Generic[Event]):
    """Thread for running side effects."""

    def __init__(
        self: SideEffectRunnerThread[Event],
        *,
        task_queue: queue.Queue[tuple[EventHandler[Event], Event] | None],
    ) -> None:
        """Initialize the side effect runner thread."""
        super().__init__()
        self.task_queue = task_queue
        self._tasks: set[Task] = set()

    def run(self: SideEffectRunnerThread[Event]) -> None:
        """Run the side effect runner thread."""
        self.loop = asyncio.new_event_loop()
        self.create_task = lambda coro: self._tasks.add(self.loop.create_task(coro))
        self.loop.run_until_complete(self.work())

    async def work(self: SideEffectRunnerThread[Event]) -> None:
        """Run the side effects."""
        while True:
            task = self.task_queue.get()
            if task is None:
                self.task_queue.task_done()
                break
            try:
                event_handler_, event = task
                if isinstance(event_handler_, weakref.ref):
                    event_handler = event_handler_()
                    if event_handler is None:
                        continue
                else:
                    event_handler = event_handler_
                parameters = 1
                with contextlib.suppress(Exception):
                    parameters = len(signature(event_handler).parameters)
                if parameters == 1:
                    result = cast(Callable[[Event], Any], event_handler)(event)
                else:
                    result = cast(Callable[[], Any], event_handler)()
                if iscoroutine(result):
                    self.create_task(result)
            finally:
                self.task_queue.task_done()
        await self.clean_up()

    async def clean_up(self: SideEffectRunnerThread[Event]) -> None:
        """Clean up the side effect runner thread."""
        while True:
            tasks = [
                task
                for task in asyncio.all_tasks(self.loop)
                if task is not asyncio.current_task(self.loop)
            ]
            if not tasks:
                break
            for task in tasks:
                await task
