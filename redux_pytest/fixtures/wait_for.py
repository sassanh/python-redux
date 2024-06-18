"""Fixture for waiting for a condition to be met."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Callable,
    Coroutine,
    Generator,
    Literal,
    TypeAlias,
    overload,
)

import pytest
from tenacity import AsyncRetrying, retry, stop_after_delay, wait_exponential

if TYPE_CHECKING:
    from asyncio.tasks import Task

    from tenacity.stop import StopBaseT
    from tenacity.wait import WaitBaseT

Waiter: TypeAlias = Callable[[], None]
AsyncWaiter: TypeAlias = Callable[[], Coroutine[None, None, None]]


class WaitFor:
    """Wait for a condition to be met."""

    def __init__(self: WaitFor) -> None:
        """Initialize the `WaitFor` context."""
        self.tasks: set[Task] = set()

    @overload
    def __call__(
        self: WaitFor,
        *,
        stop: StopBaseT | None = None,
        wait: WaitBaseT | None = None,
    ) -> Callable[[Callable[[], None]], Waiter]: ...

    @overload
    def __call__(
        self: WaitFor,
        check: Callable[[], None],
        *,
        stop: StopBaseT | None = None,
        wait: WaitBaseT | None = None,
    ) -> Waiter: ...

    @overload
    def __call__(
        self: WaitFor,
        *,
        timeout: float | None = None,
        wait: WaitBaseT | None = None,
    ) -> Callable[[Callable[[], None]], Waiter]: ...

    @overload
    def __call__(
        self: WaitFor,
        check: Callable[[], None],
        *,
        timeout: float | None = None,
        wait: WaitBaseT | None = None,
    ) -> Waiter: ...

    @overload
    def __call__(
        self: WaitFor,
        *,
        stop: StopBaseT | None = None,
        wait: WaitBaseT | None = None,
        run_async: Literal[True],
    ) -> Callable[[Callable[[], None]], AsyncWaiter]: ...

    @overload
    def __call__(
        self: WaitFor,
        check: Callable[[], None],
        *,
        stop: StopBaseT | None = None,
        wait: WaitBaseT | None = None,
        run_async: Literal[True],
    ) -> AsyncWaiter: ...

    @overload
    def __call__(
        self: WaitFor,
        *,
        timeout: float | None = None,
        wait: WaitBaseT | None = None,
        run_async: Literal[True],
    ) -> Callable[[Callable[[], None]], AsyncWaiter]: ...

    @overload
    def __call__(
        self: WaitFor,
        check: Callable[[], None],
        *,
        timeout: float | None = None,
        wait: WaitBaseT | None = None,
        run_async: Literal[True],
    ) -> AsyncWaiter: ...

    def __call__(  # noqa: PLR0913
        self: WaitFor,
        check: Callable[[], None] | None = None,
        *,
        timeout: float | None = None,
        stop: StopBaseT | None = None,
        wait: WaitBaseT | None = None,
        run_async: bool = False,
    ) -> (
        Callable[[Callable[[], None]], Waiter]
        | Waiter
        | Callable[[Callable[[], None]], AsyncWaiter]
        | AsyncWaiter
    ):
        """Create a waiter for a condition to be met."""
        args = {}
        if timeout is not None:
            args['stop'] = stop_after_delay(timeout)
        elif stop:
            args['stop'] = stop

        args['wait'] = wait or wait_exponential(multiplier=0.5)

        if run_async:

            def async_decorator(check: Callable[[], None]) -> AsyncWaiter:
                async def async_wrapper() -> None:
                    async for attempt in AsyncRetrying(**args):
                        with attempt:
                            check()

                return async_wrapper

            return async_decorator(check) if check else async_decorator

        def decorator(check: Callable[[], None]) -> Waiter:
            @retry(**args)
            def wrapper() -> None:
                check()

            return wrapper

        return decorator(check) if check else decorator


@pytest.fixture()
def wait_for() -> Generator[WaitFor, None, None]:
    """Provide `wait_for` decorator."""
    context = WaitFor()
    yield context
    del context.tasks
