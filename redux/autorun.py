# ruff: noqa: D100, D101, D102, D103, D104, D105, D107
from __future__ import annotations

import functools
import inspect
import weakref
from asyncio import Future, Task, iscoroutine, iscoroutinefunction
from typing import TYPE_CHECKING, Any, Callable, Concatenate, Generic, cast

from redux.basic_types import (
    Action,
    AutorunArgs,
    AutorunOptions,
    AutorunOriginalReturnType,
    ComparatorOutput,
    Event,
    SelectorOutput,
    State,
)

if TYPE_CHECKING:
    from redux.main import Store


class Autorun(
    Generic[
        State,
        Action,
        Event,
        SelectorOutput,
        ComparatorOutput,
        AutorunOriginalReturnType,
        AutorunArgs,
    ],
):
    def __init__(  # noqa: PLR0913
        self: Autorun,
        *,
        store: Store[State, Action, Event],
        selector: Callable[[State], SelectorOutput],
        comparator: Callable[[State], Any] | None,
        func: Callable[
            Concatenate[SelectorOutput, AutorunArgs],
            AutorunOriginalReturnType,
        ],
        options: AutorunOptions[AutorunOriginalReturnType],
    ) -> None:
        if not options.reactive and options.auto_call:
            msg = '`reactive` must be `True` if `auto_call` is `True`'
            raise ValueError(msg)
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
        self._options = options

        self._last_selector_result: SelectorOutput | None = None
        self._last_comparator_result: ComparatorOutput = cast(
            ComparatorOutput,
            object(),
        )
        if iscoroutinefunction(func):
            self._latest_value = Future()
            self._latest_value.set_result(options.default_value)
        else:
            self._latest_value: AutorunOriginalReturnType = options.default_value
        self._subscriptions: set[
            Callable[[AutorunOriginalReturnType], Any]
            | weakref.ref[Callable[[AutorunOriginalReturnType], Any]]
        ] = set()

        if self._check(store._state) and self._options.initial_call:  # noqa: SLF001
            self._call()

        if self._options.reactive:
            self._unsubscribe = store.subscribe(
                lambda state: self._call()
                if self._check(state) and self._options.auto_call
                else None,
            )
        else:
            self._unsubscribe = None

    def unsubscribe(self: Autorun, _: weakref.ref | None = None) -> None:
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
            AutorunOriginalReturnType,
            AutorunArgs,
        ],
    ) -> None:
        for subscriber_ in self._subscriptions.copy():
            if isinstance(subscriber_, weakref.ref):
                subscriber = subscriber_()
                if subscriber is None:
                    self._subscriptions.discard(subscriber_)
                    continue
            else:
                subscriber = subscriber_
            subscriber(self._latest_value)

    def _task_callback(
        self: Autorun[
            State,
            Action,
            Event,
            SelectorOutput,
            ComparatorOutput,
            AutorunOriginalReturnType,
            AutorunArgs,
        ],
        task: Task,
        *,
        future: Future | None,
    ) -> None:
        task.add_done_callback(
            lambda result: (
                future.set_result(result.result()) if future else None,
                self.inform_subscribers(),
            ),
        )

    def _check(
        self: Autorun[
            State,
            Action,
            Event,
            SelectorOutput,
            ComparatorOutput,
            AutorunOriginalReturnType,
            AutorunArgs,
        ],
        state: State | None,
    ) -> bool:
        if state is None:
            return False
        try:
            selector_result = self._selector(state)
        except AttributeError:
            return False
        if self._comparator is None:
            comparator_result = cast(ComparatorOutput, selector_result)
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

    def _call(
        self: Autorun[
            State,
            Action,
            Event,
            SelectorOutput,
            ComparatorOutput,
            AutorunOriginalReturnType,
            AutorunArgs,
        ],
        *args: AutorunArgs.args,
        **kwargs: AutorunArgs.kwargs,
    ) -> None:
        self._should_be_called = False
        func = self._func() if isinstance(self._func, weakref.ref) else self._func
        if func:
            value: AutorunOriginalReturnType = func(
                self._last_selector_result,
                *args,
                **kwargs,
            )
            create_task = self._store._create_task  # noqa: SLF001
            if iscoroutine(value) and create_task:
                future = Future()
                self._latest_value = cast(AutorunOriginalReturnType, future)
                create_task(
                    value,
                    callback=functools.partial(
                        self._task_callback,
                        future=future,
                    ),
                )
            else:
                self._latest_value = value
            self.inform_subscribers()

    def __call__(
        self: Autorun[
            State,
            Action,
            Event,
            SelectorOutput,
            ComparatorOutput,
            AutorunOriginalReturnType,
            AutorunArgs,
        ],
        *args: AutorunArgs.args,
        **kwargs: AutorunArgs.kwargs,
    ) -> AutorunOriginalReturnType:
        state = self._store._state  # noqa: SLF001
        if self._check(state) or self._should_be_called or args or kwargs:
            self._call(*args, **kwargs)
        return cast(AutorunOriginalReturnType, self._latest_value)

    def __repr__(
        self: Autorun[
            State,
            Action,
            Event,
            SelectorOutput,
            ComparatorOutput,
            AutorunOriginalReturnType,
            AutorunArgs,
        ],
    ) -> str:
        return f"""{super().__repr__()}(func: {self._func}, last_value: {
        self._latest_value})"""

    @property
    def value(
        self: Autorun[
            State,
            Action,
            Event,
            SelectorOutput,
            ComparatorOutput,
            AutorunOriginalReturnType,
            AutorunArgs,
        ],
    ) -> AutorunOriginalReturnType:
        return cast(AutorunOriginalReturnType, self._latest_value)

    def subscribe(
        self: Autorun[
            State,
            Action,
            Event,
            SelectorOutput,
            ComparatorOutput,
            AutorunOriginalReturnType,
            AutorunArgs,
        ],
        callback: Callable[[AutorunOriginalReturnType], Any],
        *,
        initial_run: bool | None = None,
        keep_ref: bool | None = None,
    ) -> Callable[[], None]:
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

        if initial_run:
            callback(self.value)

        def unsubscribe() -> None:
            self._subscriptions.discard(callback_ref)

        return unsubscribe
