# ruff: noqa: D100, D101, D102, D103, D104, D105, D107
from __future__ import annotations

import inspect
import weakref
from asyncio import Task, iscoroutine
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
        self._latest_value: AutorunOriginalReturnType = options.default_value
        self._subscriptions: set[
            Callable[[AutorunOriginalReturnType], Any]
            | weakref.ref[Callable[[AutorunOriginalReturnType], Any]]
        ] = set()

        self._check_and_call(store._state, self._options.initial_call)  # noqa: SLF001

        if self._options.reactive:
            self._unsubscribe = store.subscribe(
                lambda state: self._check_and_call(state, self._options.auto_call),
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
    ) -> None:
        task.add_done_callback(lambda _: self.inform_subscribers())
        self._latest_value = cast(AutorunOriginalReturnType, task)

    def _check_and_call(
        self: Autorun[
            State,
            Action,
            Event,
            SelectorOutput,
            ComparatorOutput,
            AutorunOriginalReturnType,
            AutorunArgs,
        ],
        state: State,
        _call: bool,  # noqa: FBT001
        *args: AutorunArgs.args,
        **kwargs: AutorunArgs.kwargs,
    ) -> None:
        try:
            selector_result = self._selector(state)
        except AttributeError:
            return
        if self._comparator is None:
            comparator_result = cast(ComparatorOutput, selector_result)
        else:
            try:
                comparator_result = self._comparator(state)
            except AttributeError:
                return
        if self._should_be_called or comparator_result != self._last_comparator_result:
            self._last_selector_result = selector_result
            self._last_comparator_result = comparator_result
            self._should_be_called = not _call
            if _call:
                func = (
                    self._func() if isinstance(self._func, weakref.ref) else self._func
                )
                if func:
                    self._latest_value = func(selector_result, *args, **kwargs)
                    create_task = self._store._create_task  # noqa: SLF001
                    if iscoroutine(self._latest_value) and create_task:
                        create_task(self._latest_value, callback=self._task_callback)
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
        if state is not None:
            self._check_and_call(state, True, *args, **kwargs)  # noqa: FBT003
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
