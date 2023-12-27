# ruff: noqa: D100, D101, D102, D103, D104, D105, D107
from __future__ import annotations

import queue
import threading
from collections import defaultdict
from inspect import signature
from threading import Lock
from typing import (
    Any,
    Callable,
    Generic,
    Protocol,
    cast,
)

from .basic_types import (
    Action,
    AutorunOriginalReturnType,
    AutorunOriginalReturnType_co,
    BaseAction,
    BaseEvent,
    ComparatorOutput,
    Event,
    EventHandler,
    EventSubscriptionOptions,
    FinishAction,
    FinishEvent,
    Immutable,
    InitAction,
    ReducerType,
    Selector,
    SelectorOutput,
    SelectorOutput_co,
    State,
    State_co,
    is_reducer_result,
    is_state,
)


class CreateStoreOptions(Immutable):
    threads: int = 5
    autorun_initial_run: bool = True
    scheduler: Callable[[Callable], Any] | None = None
    action_middleware: Callable[[BaseAction], Any] | None = None
    event_middleware: Callable[[BaseEvent], Any] | None = None


class AutorunType(Protocol, Generic[State_co]):
    def __call__(
        self: AutorunType,
        selector: Callable[[State_co], SelectorOutput],
        comparator: Selector | None = None,
    ) -> AutorunDecorator[State_co, SelectorOutput]:
        ...


class AutorunDecorator(Protocol, Generic[State_co, SelectorOutput_co]):
    def __call__(
        self: AutorunDecorator,
        func: Callable[[SelectorOutput_co], AutorunOriginalReturnType]
        | Callable[[SelectorOutput_co, SelectorOutput_co], AutorunOriginalReturnType],
    ) -> AutorunReturnType[AutorunOriginalReturnType]:
        ...


class AutorunReturnType(Protocol, Generic[AutorunOriginalReturnType_co]):
    def __call__(self: AutorunReturnType) -> AutorunOriginalReturnType_co:
        ...

    def subscribe(
        self: AutorunReturnType,
        callback: Callable[[AutorunOriginalReturnType_co], Any],
    ) -> Callable[[], None]:
        ...


class EventSubscriber(Protocol):
    def __call__(
        self: EventSubscriber,
        event_type: type[Event],
        handler: Callable[[Event], Any],
        options: EventSubscriptionOptions | None = None,
    ) -> Callable[[], None]:  # pyright: ignore[reportGeneralTypeIssues]
        ...


class InitializeStateReturnValue(Immutable, Generic[State, Action, Event]):
    dispatch: Callable[[Action | Event | list[Action | Event]], None]
    subscribe: Callable[[Callable[[State], Any]], Callable[[], None]]
    subscribe_event: EventSubscriber
    autorun: AutorunType[State]


class SideEffectRunnerThread(threading.Thread):
    def __init__(self: SideEffectRunnerThread, task_queue: queue.Queue) -> None:
        super().__init__()
        self.task_queue = task_queue

    def run(self: SideEffectRunnerThread) -> None:
        while True:
            task = self.task_queue.get()
            if task is None:
                self.task_queue.task_done()
                break

            try:
                event_handler, event = task
                event_handler(event)
            finally:
                self.task_queue.task_done()


def create_store(
    reducer: ReducerType[State, Action, Event],
    options: CreateStoreOptions | None = None,
) -> InitializeStateReturnValue[State, Action, Event]:
    _options = CreateStoreOptions() if options is None else options

    state: State
    listeners: set[Callable[[State], Any]] = set()
    event_handlers: defaultdict[
        type[Event],
        set[tuple[EventHandler, EventSubscriptionOptions]],
    ] = defaultdict(set)

    actions: list[Action] = []
    events: list[Event] = []

    event_handlers_queue = queue.Queue[tuple[EventHandler, Event] | None]()
    for _ in range(_options.threads):
        worker = SideEffectRunnerThread(event_handlers_queue)
        worker.start()

    is_running = Lock()

    def run() -> None:
        with is_running:
            nonlocal state
            while len(actions) > 0 or len(events) > 0:
                if len(actions) > 0:
                    action = actions.pop(0)
                    result = reducer(state if 'state' in locals() else None, action)
                    if is_reducer_result(result):
                        state = result.state
                        dispatch([*(result.actions or []), *(result.events or [])])
                    elif is_state(result):
                        state = result

                    if isinstance(action, FinishAction):
                        events.append(cast(Event, FinishEvent()))

                    if len(actions) == 0:
                        for listener in listeners.copy():
                            listener(state)

                if len(events) > 0:
                    event = events.pop(0)
                    for event_handler, options in event_handlers[type(event)].copy():
                        if options.run_async:
                            event_handlers_queue.put((event_handler, event))
                        else:
                            event_handler(event)

    def dispatch(items: Action | Event | list[Action | Event]) -> None:
        if isinstance(items, BaseAction):
            items = [items]

        if isinstance(items, BaseEvent):
            items = [items]

        for item in items:
            if isinstance(item, BaseAction):
                if _options.action_middleware:
                    _options.action_middleware(item)
                actions.append(item)
            if isinstance(item, BaseEvent):
                if _options.event_middleware:
                    _options.event_middleware(item)
                events.append(item)

        if _options.scheduler is None and not is_running.locked():
            run()

    def subscribe(listener: Callable[[State], Any]) -> Callable[[], None]:
        listeners.add(listener)
        return lambda: listeners.remove(listener)

    def subscribe_event(
        event_type: type[Event],
        handler: EventHandler,
        options: EventSubscriptionOptions | None = None,
    ) -> Callable[[], None]:
        _options = EventSubscriptionOptions() if options is None else options
        event_handlers[event_type].add((handler, _options))
        return lambda: event_handlers[event_type].remove((handler, _options))

    def handle_finish_event(_event: Event) -> None:
        for _ in range(_options.threads):
            event_handlers_queue.put(None)

    subscribe_event(cast(type[Event], FinishEvent), handle_finish_event)

    def autorun(
        selector: Callable[[State], SelectorOutput],
        comparator: Callable[[State], ComparatorOutput] | None = None,
    ) -> AutorunDecorator[State, SelectorOutput]:
        nonlocal state

        def decorator(
            func: Callable[[SelectorOutput], AutorunOriginalReturnType]
            | Callable[[SelectorOutput, SelectorOutput], AutorunOriginalReturnType],
        ) -> AutorunReturnType[AutorunOriginalReturnType]:
            last_selector_result: SelectorOutput | None = None
            last_comparator_result: ComparatorOutput = cast(ComparatorOutput, object())
            last_value: AutorunOriginalReturnType | None = None
            subscriptions: list[Callable[[AutorunOriginalReturnType], Any]] = []

            def check_and_call(state: State) -> None:
                nonlocal \
                    last_selector_result, \
                    last_comparator_result, \
                    last_value, \
                    subscriptions
                selector_result = selector(state)
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
                    for subscriber in subscriptions:
                        subscriber(last_value)

            if _options.autorun_initial_run and state is not None:
                check_and_call(state)

            subscribe(check_and_call)

            class Call:
                def __call__(self: Call) -> AutorunOriginalReturnType:
                    if state is not None:
                        check_and_call(state)
                    return cast(AutorunOriginalReturnType, last_value)

                def subscribe(
                    self: Call,
                    callback: Callable[[AutorunOriginalReturnType], Any],
                ) -> Callable[[], None]:
                    subscriptions.append(callback)

                    def unsubscribe() -> None:
                        subscriptions.remove(callback)

                    return unsubscribe

            return Call()

        return decorator

    dispatch(cast(Action, InitAction()))

    if _options.scheduler is not None:
        _options.scheduler(run)
        run()

    return InitializeStateReturnValue(
        dispatch=dispatch,
        subscribe=subscribe,
        subscribe_event=cast(Callable, subscribe_event),
        autorun=autorun,
    )
