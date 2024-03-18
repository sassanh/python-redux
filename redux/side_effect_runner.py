"""Redux store for managing state and side effects."""

from __future__ import annotations

import threading
from asyncio import iscoroutine
from inspect import signature
from typing import TYPE_CHECKING, Any, Callable, Generic, cast

from redux.basic_types import Event, EventHandler, TaskCreator

if TYPE_CHECKING:
    import queue


class SideEffectRunnerThread(threading.Thread, Generic[Event]):
    """Thread for running side effects."""

    def __init__(
        self: SideEffectRunnerThread[Event],
        *,
        task_queue: queue.Queue[tuple[EventHandler[Event], Event] | None],
        task_creator: TaskCreator,
    ) -> None:
        """Initialize the side effect runner thread."""
        super().__init__()
        self.task_queue = task_queue
        self.create_task = task_creator

    def run(self: SideEffectRunnerThread[Event]) -> None:
        """Run the side effect runner thread."""
        while True:
            task = self.task_queue.get()
            if task is None:
                self.task_queue.task_done()
                break

            try:
                event_handler, event = task
                if len(signature(event_handler).parameters) == 1:
                    result = cast(Callable[[Event], Any], event_handler)(event)
                else:
                    result = cast(Callable[[], Any], event_handler)()
                if iscoroutine(result):
                    self.create_task(result)
            finally:
                self.task_queue.task_done()
