# ruff: noqa: D100, D101, D102, D103, D104, D105, D107
from __future__ import annotations

import queue
import threading
import weakref
from collections import defaultdict
from inspect import signature
from threading import Lock
from typing import Any, Callable, Generic, cast

from .basic_types import (
    Action,
    AutorunDecorator,
    AutorunOptions,
    AutorunOriginalReturnType,
    AutorunReturnType,
    BaseAction,
    BaseEvent,
    ComparatorOutput,
    CreateStoreOptions,
    DispatchParameters,
    Event,
    Event2,
    EventHandler,
    EventSubscriptionOptions,
    FinishAction,
    FinishEvent,
    InitAction,
    InitializeStateReturnValue,
    ReducerType,
    SelectorOutput,
    State,
    is_reducer_result,
    is_state,
)


class SideEffectRunnerThread(threading.Thread, Generic[Event]):
    def __init__(
        self: SideEffectRunnerThread[Event],
        task_queue: queue.Queue[tuple[EventHandler[Event], Event] | None],
    ) -> None:
        super().__init__()
        self.task_queue = task_queue

    def run(self: SideEffectRunnerThread[Event]) -> None:
        while True:
            task = self.task_queue.get()
            if task is None:
                self.task_queue.task_done()
                break

            try:
                event_handler, event = task
                if len(signature(event_handler).parameters) == 1:
                    cast(Callable[[Event], Any], event_handler)(event)
                else:
                    cast(Callable[[], Any], event_handler)()
            finally:
                self.task_queue.task_done()


def create_store(
    reducer: ReducerType[State, Action, Event],
    options: CreateStoreOptions | None = None,
) -> InitializeStateReturnValue[State, Action, Event]:
    store_options = options or CreateStoreOptions()

    state: State | None = None
    listeners: set[Callable[[State], Any] | weakref.ref[Callable[[State], Any]]] = set()
    event_handlers: defaultdict[
        type[Event],
        set[tuple[EventHandler | weakref.ref[EventHandler], EventSubscriptionOptions]],
    ] = defaultdict(set)

    actions: list[Action] = []
    events: list[Event] = []

    event_handlers_queue = queue.Queue[tuple[EventHandler[Event], Event] | None]()
    for _ in range(store_options.threads):
        worker = SideEffectRunnerThread(event_handlers_queue)
        worker.start()

    is_running = Lock()

    def run() -> None:
        with is_running:
            nonlocal state
            while len(actions) > 0 or len(events) > 0:
                if len(actions) > 0:
                    action = actions.pop(0)
                    result = reducer(state, action)
                    if is_reducer_result(result):
                        state = result.state
                        dispatch([*(result.actions or []), *(result.events or [])])
                    elif is_state(result):
                        state = result

                    if isinstance(action, FinishAction):
                        dispatch(cast(Event, FinishEvent()))

                    if len(actions) == 0 and state:
                        for listener_ in listeners.copy():
                            if isinstance(listener_, weakref.ref):
                                listener = listener_()
                                if listener is None:
                                    listeners.remove(listener_)
                                    continue
                            else:
                                listener = listener_
                            listener(state)

                if len(events) > 0:
                    event = events.pop(0)
                    for event_handler_, options in event_handlers[type(event)].copy():
                        if isinstance(event_handler_, weakref.ref):
                            event_handler = event_handler_()
                            if event_handler is None:
                                event_handlers[type(event)].remove(
                                    (event_handler_, options),
                                )
                                continue
                        else:
                            event_handler = event_handler_
                        if options.run_async:
                            event_handlers_queue.put((event_handler, event))
                        elif len(signature(event_handler).parameters) == 1:
                            cast(Callable[[Event], Any], event_handler)(event)
                        else:
                            cast(Callable[[], Any], event_handler)()

    def dispatch(
        *parameters: DispatchParameters[Action, Event],
        with_state: Callable[[State | None], DispatchParameters[Action, Event]]
        | None = None,
    ) -> None:
        if with_state is not None:
            dispatch(with_state(state))

        items = [
            item
            for items in parameters
            for item in (items if isinstance(items, list) else [items])
        ]

        for item in items:
            if isinstance(item, BaseAction):
                if store_options.action_middleware:
                    store_options.action_middleware(item)
                actions.append(item)
            if isinstance(item, BaseEvent):
                if store_options.event_middleware:
                    store_options.event_middleware(item)
                events.append(item)

        if store_options.scheduler is None and not is_running.locked():
            run()

    def subscribe(
        listener: Callable[[State], Any],
        *,
        keep_ref: bool = True,
    ) -> Callable[[], None]:
        listener_ref = listener if keep_ref else weakref.ref(listener)

        listeners.add(listener_ref)
        return lambda: listeners.remove(listener_ref)

    def subscribe_event(
        event_type: type[Event2],
        handler: EventHandler[Event2],
        *,
        options: EventSubscriptionOptions | None = None,
    ) -> Callable[[], None]:
        subscription_options = (
            EventSubscriptionOptions() if options is None else options
        )

        handler_ref = handler if subscription_options.keep_ref else weakref.ref(handler)

        event_handlers[cast(type[Event], event_type)].add(
            (handler_ref, subscription_options),
        )
        return lambda: event_handlers[cast(type[Event], event_type)].remove(
            (handler_ref, subscription_options),
        )

    def handle_finish_event(_event: Event) -> None:
        for _ in range(store_options.threads):
            event_handlers_queue.put(None)

    subscribe_event(cast(type[Event], FinishEvent), handle_finish_event)

    def autorun(
        selector: Callable[[State], SelectorOutput],
        comparator: Callable[[State], ComparatorOutput] | None = None,
        *,
        options: AutorunOptions[AutorunOriginalReturnType] | None = None,
    ) -> AutorunDecorator[
        State,
        SelectorOutput,
        AutorunOriginalReturnType,
    ]:
        autorun_options = options or AutorunOptions()
        nonlocal state

        def decorator(
            func: Callable[[SelectorOutput], AutorunOriginalReturnType]
            | Callable[[SelectorOutput, SelectorOutput], AutorunOriginalReturnType],
        ) -> AutorunReturnType[AutorunOriginalReturnType]:
            last_selector_result: SelectorOutput | None = None
            last_comparator_result: ComparatorOutput = cast(ComparatorOutput, object())
            last_value: AutorunOriginalReturnType | None = autorun_options.default_value
            subscriptions: set[
                Callable[[AutorunOriginalReturnType], Any]
                | weakref.ref[Callable[[AutorunOriginalReturnType], Any]]
            ] = set()

            def check_and_call(state: State) -> None:
                nonlocal \
                    last_selector_result, \
                    last_comparator_result, \
                    last_value, \
                    subscriptions
                try:
                    selector_result = selector(state)
                except AttributeError:
                    return
                if comparator is None:
                    comparator_result = cast(ComparatorOutput, selector_result)
                else:
                    comparator_result = comparator(state)
                if comparator_result != last_comparator_result:
                    previous_result = last_selector_result
                    last_selector_result = selector_result
                    last_comparator_result = comparator_result
                    if len(signature(func).parameters) == 1:
                        last_value = cast(
                            Callable[[SelectorOutput], AutorunOriginalReturnType],
                            func,
                        )(selector_result)
                    else:
                        last_value = cast(
                            Callable[
                                [SelectorOutput, SelectorOutput | None],
                                AutorunOriginalReturnType,
                            ],
                            func,
                        )(
                            selector_result,
                            previous_result,
                        )
                    for subscriber_ in subscriptions.copy():
                        if isinstance(subscriber_, weakref.ref):
                            subscriber = subscriber_()
                            if subscriber is None:
                                subscriptions.remove(subscriber_)
                                continue
                        else:
                            subscriber = subscriber_
                        subscriber(last_value)

            if autorun_options.initial_run and state is not None:
                check_and_call(state)

            subscribe(check_and_call)

            class Call:
                def __call__(self: Call) -> AutorunOriginalReturnType:
                    if state is not None:
                        check_and_call(state)
                    return cast(AutorunOriginalReturnType, last_value)

                @property
                def value(self: Call) -> AutorunOriginalReturnType:
                    return cast(AutorunOriginalReturnType, last_value)

                def subscribe(
                    self: Call,
                    callback: Callable[[AutorunOriginalReturnType], Any],
                    *,
                    immediate_run: bool
                    | None = autorun_options.subscribers_immediate_run,
                    keep_ref: bool | None = autorun_options.subscribers_keep_ref,
                ) -> Callable[[], None]:
                    callback_ref = callback if keep_ref else weakref.ref(callback)
                    subscriptions.add(callback_ref)

                    if immediate_run:
                        callback(self.value)

                    def unsubscribe() -> None:
                        subscriptions.remove(callback_ref)

                    return unsubscribe

            return Call()

        return decorator

    if store_options.auto_init:
        if store_options.scheduler:
            store_options.scheduler(
                lambda: dispatch(cast(Action, InitAction())),
                interval=False,
            )
        else:
            dispatch(cast(Action, InitAction()))

    if store_options.scheduler:
        store_options.scheduler(run, interval=True)

    return InitializeStateReturnValue(
        dispatch=dispatch,
        subscribe=subscribe,
        subscribe_event=subscribe_event,
        autorun=autorun,
    )
