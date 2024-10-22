"""Fixture for waiting for a condition to be met."""

from __future__ import annotations

from collections.abc import Callable, Coroutine, Generator
from typing import (
    TYPE_CHECKING,
    Literal,
    ParamSpec,
    TypeAlias,
    overload,
)

import pytest
from tenacity import AsyncRetrying, retry, stop_after_delay, wait_exponential

if TYPE_CHECKING:
    from asyncio.tasks import Task

    from tenacity.stop import StopBaseT
    from tenacity.wait import WaitBaseT

WaitForArgs = ParamSpec('WaitForArgs')

Waiter: TypeAlias = Callable[WaitForArgs, None]
AsyncWaiter: TypeAlias = Callable[WaitForArgs, Coroutine[None, None, None]]


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
    ) -> Callable[[Callable[WaitForArgs, None]], Waiter[WaitForArgs]]: ...

    @overload
    def __call__(
        self: WaitFor,
        check: Callable[WaitForArgs, None],
        *,
        stop: StopBaseT | None = None,
        wait: WaitBaseT | None = None,
    ) -> Waiter[WaitForArgs]: ...

    @overload
    def __call__(
        self: WaitFor,
        *,
        timeout: float | None = None,
        wait: WaitBaseT | None = None,
    ) -> Callable[[Callable[WaitForArgs, None]], Waiter[WaitForArgs]]: ...

    @overload
    def __call__(
        self: WaitFor,
        check: Callable[WaitForArgs, None],
        *,
        timeout: float | None = None,
        wait: WaitBaseT | None = None,
    ) -> Waiter[WaitForArgs]: ...

    @overload
    def __call__(
        self: WaitFor,
        *,
        stop: StopBaseT | None = None,
        wait: WaitBaseT | None = None,
        run_async: Literal[True],
    ) -> Callable[[Callable[WaitForArgs, None]], AsyncWaiter[WaitForArgs]]: ...

    @overload
    def __call__(
        self: WaitFor,
        check: Callable[WaitForArgs, None],
        *,
        stop: StopBaseT | None = None,
        wait: WaitBaseT | None = None,
        run_async: Literal[True],
    ) -> AsyncWaiter[WaitForArgs]: ...

    @overload
    def __call__(
        self: WaitFor,
        *,
        timeout: float | None = None,
        wait: WaitBaseT | None = None,
        run_async: Literal[True],
    ) -> Callable[[Callable[WaitForArgs, None]], AsyncWaiter[WaitForArgs]]: ...

    @overload
    def __call__(
        self: WaitFor,
        check: Callable[WaitForArgs, None],
        *,
        timeout: float | None = None,
        wait: WaitBaseT | None = None,
        run_async: Literal[True],
    ) -> AsyncWaiter[WaitForArgs]: ...

    def __call__(
        self: WaitFor,
        check: Callable[WaitForArgs, None] | None = None,
        *,
        timeout: float | None = None,
        stop: StopBaseT | None = None,
        wait: WaitBaseT | None = None,
        run_async: bool = False,
    ) -> (
        Callable[[Callable[WaitForArgs, None]], Waiter[WaitForArgs]]
        | Waiter[WaitForArgs]
        | Callable[[Callable[WaitForArgs, None]], AsyncWaiter[WaitForArgs]]
        | AsyncWaiter[WaitForArgs]
    ):
        """Create a waiter for a condition to be met."""
        parameters = {}
        if timeout is not None:
            parameters['stop'] = stop_after_delay(timeout)
        elif stop:
            parameters['stop'] = stop

        parameters['wait'] = wait or wait_exponential(multiplier=0.5)

        if run_async:

            def async_decorator(
                check: Callable[WaitForArgs, None],
            ) -> AsyncWaiter[WaitForArgs]:
                async def async_wrapper(
                    *args: WaitForArgs.args,
                    **kwargs: WaitForArgs.kwargs,
                ) -> None:
                    async for attempt in AsyncRetrying(**parameters):
                        with attempt:
                            check(*args, **kwargs)

                return async_wrapper

            return async_decorator(check) if check else async_decorator

        def decorator(check: Callable[WaitForArgs, None]) -> Waiter[WaitForArgs]:
            @retry(**parameters)
            def wrapper(*args: WaitForArgs.args, **kwargs: WaitForArgs.kwargs) -> None:
                check(*args, **kwargs)

            return wrapper

        return decorator(check) if check else decorator


@pytest.fixture
def wait_for() -> Generator[WaitFor, None, None]:
    """Provide `wait_for` decorator."""
    context = WaitFor()
    yield context
    del context.tasks
