# ruff: noqa: D100, D101, D102, D103, D104, D105, D107
from __future__ import annotations

import inspect
import weakref
from asyncio import iscoroutinefunction
from inspect import signature
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Generic, cast

from redux.basic_types import (
    Action,
    AutorunOptions,
    AutorunOriginalReturnType,
    ComparatorOutput,
    Event,
    SelectorOutput,
    State,
)

if TYPE_CHECKING:
    from types import MethodType

    from redux.main import Store


class Autorun(
    Generic[
        State,
        Action,
        Event,
        SelectorOutput,
        ComparatorOutput,
        AutorunOriginalReturnType,
    ],
):
    def __init__(  # noqa: PLR0913
        self: Autorun,
        *,
        store: Store[State, Action, Event],
        selector: Callable[[State], SelectorOutput],
        comparator: Callable[[State], Any] | None,
        func: Callable[[SelectorOutput], AutorunOriginalReturnType]
        | Callable[[SelectorOutput, SelectorOutput], AutorunOriginalReturnType],
        options: AutorunOptions[AutorunOriginalReturnType],
    ) -> None:
        self._store = store
        self._selector = selector
        self._comparator = comparator
        if options.keep_ref:
            self._func = func
        elif inspect.ismethod(func):
            self._func = weakref.WeakMethod(func)
        else:
            self._func = weakref.ref(func)
        self._options = options

        self._last_selector_result: SelectorOutput | None = None
        self._last_comparator_result: ComparatorOutput = cast(
            ComparatorOutput,
            object(),
        )
        self._latest_value: AutorunOriginalReturnType = options.default_value
        self._subscriptions: set[
            Callable[[AutorunOriginalReturnType], Any]
            | weakref.ref[Callable[[AutorunOriginalReturnType], Any]]
        ] = set()

        if self._options.initial_run and store._state is not None:  # noqa: SLF001
            self._check_and_call(store._state)  # noqa: SLF001

        store.subscribe(self._check_and_call, keep_ref=options.keep_ref)

    def inform_subscribers(
        self: Autorun[
            State,
            Action,
            Event,
            SelectorOutput,
            ComparatorOutput,
            AutorunOriginalReturnType,
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

    def call_func(
        self: Autorun[
            State,
            Action,
            Event,
            SelectorOutput,
            ComparatorOutput,
            AutorunOriginalReturnType,
        ],
        selector_result: SelectorOutput,
        previous_result: SelectorOutput | None,
        func: Callable[
            [SelectorOutput, SelectorOutput],
            AutorunOriginalReturnType,
        ]
        | Callable[[SelectorOutput], AutorunOriginalReturnType]
        | MethodType,
    ) -> AutorunOriginalReturnType:
        if len(signature(func).parameters) == 1:
            return cast(
                Callable[[SelectorOutput], AutorunOriginalReturnType],
                func,
            )(selector_result)
        return cast(
            Callable[
                [SelectorOutput, SelectorOutput | None],
                AutorunOriginalReturnType,
            ],
            func,
        )(selector_result, previous_result)

    def _check_and_call(
        self: Autorun[
            State,
            Action,
            Event,
            SelectorOutput,
            ComparatorOutput,
            AutorunOriginalReturnType,
        ],
        state: State,
    ) -> None:
        try:
            selector_result = self._selector(state)
        except AttributeError:
            return
        func = self._func() if isinstance(self._func, weakref.ref) else self._func
        if func:
            if self._comparator is None:
                comparator_result = cast(ComparatorOutput, selector_result)
            else:
                try:
                    comparator_result = self._comparator(state)
                except AttributeError:
                    return
            if comparator_result != self._last_comparator_result:
                previous_result = self._last_selector_result
                self._last_selector_result = selector_result
                self._last_comparator_result = comparator_result
                self._latest_value = self.call_func(
                    selector_result,
                    previous_result,
                    func,
                )
                if iscoroutinefunction(func):
                    task = self._store._async_loop.create_task(  # noqa: SLF001
                        cast(Coroutine, self._latest_value),
                    )
                    task.add_done_callback(lambda _: self.inform_subscribers())
                    self._latest_value = cast(AutorunOriginalReturnType, task)
                else:
                    self.inform_subscribers()

    def __call__(
        self: Autorun[
            State,
            Action,
            Event,
            SelectorOutput,
            ComparatorOutput,
            AutorunOriginalReturnType,
        ],
    ) -> AutorunOriginalReturnType:
        state = self._store._state  # noqa: SLF001
        if state is not None:
            self._check_and_call(state)
        return cast(AutorunOriginalReturnType, self._latest_value)

    def __repr__(
        self: Autorun[
            State,
            Action,
            Event,
            SelectorOutput,
            ComparatorOutput,
            AutorunOriginalReturnType,
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
            callback = (
                callback_ref()
                if isinstance(callback_ref, weakref.ref)
                else callback_ref
            )
            if callback is not None:
                self._subscriptions.discard(callback)

        return unsubscribe
