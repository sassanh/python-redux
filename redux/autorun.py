"""Redux autorun module."""

from __future__ import annotations

import asyncio
import functools
import inspect
import weakref
from asyncio import iscoroutine, iscoroutinefunction
from typing import (
    TYPE_CHECKING,
    Any,
    Concatenate,
    Generic,
    Literal,
    cast,
)

from redux.basic_types import (
    NOT_SET,
    Action,
    Args,
    AutoAwait,
    AutorunOptionsType,
    ComparatorOutput,
    Event,
    ReturnType,
    SelectorOutput,
    State,
    T,
)
from redux.utils import call_func, signature_without_selector

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Generator

    from redux.main import Store


class AwaitableWrapper(Generic[T]):
    """A wrapper for a coroutine to track if it has been awaited."""

    _unawaited = object()
    value: tuple[Literal[False], None] | tuple[Literal[True], T]

    def __init__(self, coro: Coroutine[None, None, T]) -> None:
        """Initialize the AwaitableWrapper with a coroutine."""
        self.coro = coro
        self.value = (False, None)

    def __await__(self) -> Generator[None, None, T]:
        """Await the coroutine and set the awaited flag to True."""
        return self._wrap().__await__()

    async def _wrap(self) -> T:
        """Wrap the coroutine and set the awaited flag to True."""
        if self.value[0] is True:
            return self.value[1]
        self.value = (True, await self.coro)
        return self.value[1]

    def close(self) -> None:
        """Close the coroutine if it has not been awaited."""
        self.coro.close()

    @property
    def awaited(self) -> bool:
        """Check if the coroutine has been awaited."""
        return self.value[0] is True

    def __repr__(self) -> str:
        """Return a string representation of the AwaitableWrapper."""
        return f'AwaitableWrapper({self.coro}, awaited={self.awaited})'


class Autorun(
    Generic[
        State,
        Action,
        Event,
        SelectorOutput,
        ComparatorOutput,
        Args,
        ReturnType,
    ],
):
    """Run a wrapped function in response to specific state changes in the store."""

    def __init__(  # noqa: C901, PLR0912
        self: Autorun,
        *,
        store: Store[State, Action, Event],
        selector: Callable[[State], SelectorOutput],
        comparator: Callable[[State], Any] | None,
        func: Callable[
            Concatenate[SelectorOutput, Args],
            ReturnType,
        ],
        options: AutorunOptionsType[ReturnType, AutoAwait],
    ) -> None:
        """Initialize the Autorun instance."""
        if hasattr(func, '__name__'):
            self.__name__ = f'Autorun:{func.__name__}'
        else:
            self.__name__ = f'Autorun:{func}'
        if hasattr(func, '__qualname__'):
            self.__qualname__ = f'Autorun:{func.__qualname__}'
        else:
            self.__qualname__ = f'Autorun:{func}'
        self.__signature__ = signature_without_selector(func)
        self.__module__ = func.__module__
        if (annotations := getattr(func, '__annotations__', None)) is not None:
            self.__annotations__ = annotations
        if (defaults := getattr(func, '__defaults__', None)) is not None:
            self.__defaults__ = defaults
        if (kwdefaults := getattr(func, '__kwdefaults__', None)) is not None:
            self.__kwdefaults__ = kwdefaults

        self._store = store
        self._selector = selector
        self._comparator = comparator
        self._should_be_called = False

        if options.keep_ref:
            self._func = func
        elif inspect.ismethod(func):
            self._func = weakref.WeakMethod(func, self.unsubscribe)
        else:
            self._func = weakref.ref(func, self.unsubscribe)
        self._is_coroutine = (
            asyncio.coroutines._is_coroutine  # type: ignore [reportAttributeAccessIssue]  # noqa: SLF001
            if asyncio.iscoroutinefunction(func) and options.auto_await is False
            else None
        )
        self._options = options

        self._last_selector_result: SelectorOutput | None = NOT_SET
        self._last_comparator_result: ComparatorOutput = cast(
            'ComparatorOutput',
            object(),
        )
        if iscoroutinefunction(func):

            async def default_value_wrapper() -> ReturnType | None:
                return options.default_value

            default_value = default_value_wrapper()

            self._create_task(default_value)
            self._latest_value: ReturnType = default_value
        else:
            self._latest_value: ReturnType = options.default_value
        self._subscriptions: set[
            Callable[[ReturnType], Any] | weakref.ref[Callable[[ReturnType], Any]]
        ] = set()

        if (
            store.with_state(lambda state: state, ignore_uninitialized_store=True)(
                self.check,
            )()
            and self._options.initial_call
        ):
            self._should_be_called = False
            self.call()

        if self._options.reactive:
            self._unsubscribe = store._subscribe(self.react)  # noqa: SLF001
        else:
            self._unsubscribe = None

    def _create_task(self: Autorun, coro: Coroutine[None, None, Any]) -> None:
        """Create a task for the coroutine."""
        if self._store.store_options.task_creator:
            self._store.store_options.task_creator(coro)

    def react(
        self: Autorun,
        state: State,
    ) -> None:
        """React to state changes in the store."""
        if self._options.reactive and self.check(state):
            self._should_be_called = False
            self.call()

    def unsubscribe(
        self: Autorun[
            State,
            Action,
            Event,
            SelectorOutput,
            ComparatorOutput,
            Args,
            ReturnType,
        ],
        _: weakref.ref | None = None,
    ) -> None:
        """Unsubscribe the autorun from the store and clean up resources."""
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None

    def inform_subscribers(
        self: Autorun[
            State,
            Action,
            Event,
            SelectorOutput,
            ComparatorOutput,
            Args,
            ReturnType,
        ],
    ) -> None:
        """Inform all subscribers about the latest value."""
        for subscriber_ in self._subscriptions.copy():
            if isinstance(subscriber_, weakref.ref):
                subscriber = subscriber_()
                if subscriber is None:
                    self._subscriptions.discard(subscriber_)
                    continue
            else:
                subscriber = subscriber_
            subscriber(self._latest_value)

    def check(
        self: Autorun[
            State,
            Action,
            Event,
            SelectorOutput,
            ComparatorOutput,
            Args,
            ReturnType,
        ],
        state: State,
    ) -> bool:
        """Check if the autorun should be called based on the current state."""
        try:
            selector_result = self._selector(state)
        except AttributeError:
            return False
        if self._comparator is None:
            comparator_result = cast('ComparatorOutput', selector_result)
        else:
            try:
                comparator_result = self._comparator(state)
            except AttributeError:
                return False
        self._should_be_called = (
            self._should_be_called or comparator_result != self._last_comparator_result
        )
        self._last_selector_result = selector_result
        self._last_comparator_result = comparator_result
        return self._should_be_called

    def call(
        self: Autorun[
            State,
            Action,
            Event,
            SelectorOutput,
            ComparatorOutput,
            Args,
            ReturnType,
        ],
        *args: Args.args,
        **kwargs: Args.kwargs,
    ) -> None:
        """Call the wrapped function with the current state of the store."""
        func = self._func() if isinstance(self._func, weakref.ref) else self._func
        if func and self._last_selector_result is not NOT_SET:
            value: ReturnType = call_func(
                func,
                [self._last_selector_result],
                *args,
                **kwargs,
            )
            previous_value = self._latest_value
            if iscoroutine(value):
                if (
                    self._options.auto_await
                    is False  # only explicit `False` disables auto-await, not `None`
                ):
                    if (
                        self._latest_value is not NOT_SET
                        and isinstance(self._latest_value, AwaitableWrapper)
                        and not self._latest_value.awaited
                    ):
                        self._latest_value.close()
                    self._latest_value = cast('ReturnType', AwaitableWrapper(value))
                else:
                    self._latest_value = cast('ReturnType', None)
                    self._create_task(value)
            else:
                self._latest_value = value
            if self._latest_value is not previous_value:
                self.inform_subscribers()

    def __call__(
        self: Autorun[
            State,
            Action,
            Event,
            SelectorOutput,
            ComparatorOutput,
            Args,
            ReturnType,
        ],
        *args: Args.args,
        **kwargs: Args.kwargs,
    ) -> ReturnType:
        """Call the wrapped function with the current state of the store."""
        self._store.with_state(lambda state: state, ignore_uninitialized_store=True)(
            self.check,
        )()
        if self._should_be_called or args or kwargs or not self._options.memoization:
            self._should_be_called = False
            self.call(*args, **kwargs)
        return self._latest_value

    def __repr__(
        self: Autorun[
            State,
            Action,
            Event,
            SelectorOutput,
            ComparatorOutput,
            Args,
            ReturnType,
        ],
    ) -> str:
        """Return a string representation of the Autorun instance."""
        return (
            super().__repr__()
            + f'(func: {self._func}, last_value: {self._latest_value})'
        )

    @property
    def value(
        self: Autorun[
            State,
            Action,
            Event,
            SelectorOutput,
            ComparatorOutput,
            Args,
            ReturnType,
        ],
    ) -> ReturnType:
        """Get the latest value of the autorun function."""
        return self._latest_value

    def subscribe(
        self: Autorun[
            State,
            Action,
            Event,
            SelectorOutput,
            ComparatorOutput,
            Args,
            ReturnType,
        ],
        callback: Callable[[ReturnType], Any],
        *,
        initial_run: bool | None = None,
        keep_ref: bool | None = None,
    ) -> Callable[[], None]:
        """Subscribe to the autorun to be notified of changes in the state."""
        if initial_run is None:
            initial_run = self._options.subscribers_initial_run
        if keep_ref is None:
            keep_ref = self._options.subscribers_keep_ref
        if keep_ref:
            callback_ref = callback
        elif inspect.ismethod(callback):
            callback_ref = weakref.WeakMethod(callback)
        else:
            callback_ref = weakref.ref(callback)
        self._subscriptions.add(callback_ref)

        if initial_run and self.value is not NOT_SET:
            callback(self.value)

        def unsubscribe() -> None:
            self._subscriptions.discard(callback_ref)

        return unsubscribe

    def __get__(
        self: Autorun[
            State,
            Action,
            Event,
            SelectorOutput,
            ComparatorOutput,
            Args,
            ReturnType,
        ],
        obj: object | None,
        _: type | None = None,
    ) -> Autorun[
        State,
        Action,
        Event,
        SelectorOutput,
        ComparatorOutput,
        Args,
        ReturnType,
    ]:
        """Get the autorun instance."""
        return cast('Autorun', functools.partial(self, obj))
