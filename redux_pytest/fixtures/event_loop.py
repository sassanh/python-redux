# ruff: noqa: D100, D101, D102, D103, D107
from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Coroutine


class LoopThread(threading.Thread):
    def __init__(self: LoopThread) -> None:
        super().__init__()
        self.loop = asyncio.new_event_loop()

    def run(self: LoopThread) -> None:
        self.loop.run_forever()

    def stop(self: LoopThread) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)

    def create_task(self: LoopThread, coro: Coroutine) -> None:
        self.loop.call_soon_threadsafe(self.loop.create_task, coro)


@pytest.fixture
def event_loop() -> LoopThread:
    loop_thread = LoopThread()
    loop_thread.start()
    return loop_thread
