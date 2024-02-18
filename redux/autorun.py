# ruff: noqa: D100, D101, D102, D103, D104, D105, D107
from __future__ import annotations

import weakref
from inspect import signature
from types import MethodType
from typing import TYPE_CHECKING, Any, Callable, Generic, cast

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
        self._func = func
        self.options = options

        self._last_selector_result: SelectorOutput | None = None
        self._last_comparator_result: ComparatorOutput = cast(
            ComparatorOutput,
            object(),
        )
        self._last_value: AutorunOriginalReturnType | None = options.default_value
        self._subscriptions: set[
            Callable[[AutorunOriginalReturnType], Any]
            | weakref.ref[Callable[[AutorunOriginalReturnType], Any]]
        ] = set()

        if self.options.initial_run and store._state is not None:  # noqa: SLF001
            self.check_and_call(store._state)  # noqa: SLF001

        store.subscribe(self.check_and_call)

    def check_and_call(self: Autorun, state: State) -> None:
        try:
            selector_result = self._selector(state)
        except AttributeError:
            return
        if self._comparator is None:
            comparator_result = cast(ComparatorOutput, selector_result)
        else:
            comparator_result = self._comparator(state)
        if comparator_result != self._last_comparator_result:
            previous_result = self._last_selector_result
            self._last_selector_result = selector_result
            self._last_comparator_result = comparator_result
            if len(signature(self._func).parameters) == 1:
                last_value = cast(
                    Callable[[SelectorOutput], AutorunOriginalReturnType],
                    self._func,
                )(selector_result)
            else:
                last_value = cast(
                    Callable[
                        [SelectorOutput, SelectorOutput | None],
                        AutorunOriginalReturnType,
                    ],
                    self._func,
                )(
                    selector_result,
                    previous_result,
                )
            for subscriber_ in self._subscriptions.copy():
                if isinstance(subscriber_, weakref.ref):
                    subscriber = subscriber_()
                    if subscriber is None:
                        self._subscriptions.discard(subscriber_)
                        continue
                else:
                    subscriber = subscriber_
                subscriber(last_value)

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
        if self._store._state is not None:  # noqa: SLF001
            self.check_and_call(self._store._state)  # noqa: SLF001
        return cast(AutorunOriginalReturnType, self._last_value)

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
        return cast(AutorunOriginalReturnType, self._last_value)

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
        immediate_run: bool | None = None,
        keep_ref: bool | None = None,
    ) -> Callable[[], None]:
        if immediate_run is None:
            immediate_run = self.options.subscribers_immediate_run
        if keep_ref is None:
            keep_ref = self.options.subscribers_keep_ref
        if keep_ref:
            callback_ref = callback
        elif isinstance(callback, MethodType):
            callback_ref = weakref.WeakMethod(callback)
        else:
            callback_ref = weakref.ref(callback)
        self._subscriptions.add(callback_ref)

        if immediate_run:
            callback(self.value)

        def unsubscribe() -> None:
            self._subscriptions.discard(callback_ref)

        return unsubscribe
