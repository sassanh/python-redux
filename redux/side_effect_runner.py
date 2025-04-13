"""Side effect runner thread for Redux."""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import threading
import weakref
from asyncio import Handle, iscoroutine
from typing import TYPE_CHECKING, Any, Generic, cast

from redux.basic_types import Event, EventHandler, TaskCreator

if TYPE_CHECKING:
    import queue
    from collections.abc import Callable


class SideEffectRunner(threading.Thread, Generic[Event]):
    """Thread for running side effects."""

    def __init__(
        self: SideEffectRunner,
        *,
        task_queue: queue.Queue[tuple[EventHandler[Event], Event] | None],
        create_task: TaskCreator | None,
    ) -> None:
        """Initialize the side effect runner thread."""
        super().__init__()
        self.name = 'Side Effect Runner'
        self.task_queue = task_queue
        self.loop = asyncio.get_event_loop()
        self._handles: set[Handle] = set()
        self.create_task = create_task

    def run(self: SideEffectRunner[Event]) -> None:
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
                    parameters = len(
                        [
                            param
                            for param in inspect.signature(
                                event_handler,
                            ).parameters.values()
                            if param.kind
                            in (param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD)
                        ],
                    )

                if self.create_task:

                    async def _(
                        event_handler: EventHandler[Event],
                        event: Event,
                        parameters: int,
                    ) -> None:
                        if parameters == 1:
                            result = cast('Callable[[Event], Any]', event_handler)(
                                event,
                            )
                        else:
                            result = cast('Callable[[], Any]', event_handler)()
                        if iscoroutine(result):
                            await result

                    self.create_task(_(event_handler, event, parameters))
                else:  # noqa: PLR5501
                    if parameters == 1:
                        cast('Callable[[Event], Any]', event_handler)(event)
                    else:
                        cast('Callable[[], Any]', event_handler)()
            finally:
                self.task_queue.task_done()
