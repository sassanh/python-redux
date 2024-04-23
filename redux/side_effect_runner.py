"""Redux store for managing state and side effects."""

from __future__ import annotations

import asyncio
import contextlib
import threading
import weakref
from asyncio import Handle, iscoroutine
from inspect import signature
from typing import TYPE_CHECKING, Any, Callable, Generic, cast

from redux.basic_types import Event, EventHandler

if TYPE_CHECKING:
    import queue


class SideEffectRunnerThread(threading.Thread, Generic[Event]):
    """Thread for running side effects."""

    def __init__(
        self: SideEffectRunnerThread,
        *,
        task_queue: queue.Queue[tuple[EventHandler[Event], Event] | None],
    ) -> None:
        """Initialize the side effect runner thread."""
        super().__init__()
        self.task_queue = task_queue
        self.loop = asyncio.get_event_loop()
        self._handles: set[Handle] = set()
        self.create_task = lambda coro: self._handles.add(
            self.loop.call_soon_threadsafe(self.loop.create_task, coro),
        )

    def run(self: SideEffectRunnerThread[Event]) -> None:
        """Run the side effect runner thread."""
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
