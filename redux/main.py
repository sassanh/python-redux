# ruff: noqa: D100, D101, D102, D103, D104, D105, D107
from __future__ import annotations

import queue
import threading
import weakref
from collections import defaultdict
from inspect import signature
from threading import Lock
from types import MethodType
from typing import Any, Callable, Generic, cast

from redux.autorun import Autorun
from redux.basic_types import (
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
    ReducerType,
    SelectorOutput,
    State,
    is_complete_reducer_result,
    is_state_reducer_result,
)


class _SideEffectRunnerThread(threading.Thread, Generic[Event]):
    def __init__(
        self: _SideEffectRunnerThread[Event],
        task_queue: queue.Queue[tuple[EventHandler[Event], Event] | None],
    ) -> None:
        super().__init__()
        self.task_queue = task_queue

    def run(self: _SideEffectRunnerThread[Event]) -> None:
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


class Store(Generic[State, Action, Event]):
    def __init__(
        self: Store[State, Action, Event],
        reducer: ReducerType[State, Action, Event],
        options: CreateStoreOptions | None = None,
    ) -> None:
        self.store_options = options or CreateStoreOptions()
        self.reducer = reducer

        self._state: State | None = None
        self._listeners: set[
            Callable[[State], Any] | weakref.ref[Callable[[State], Any]]
        ] = set()
        self._event_handlers: defaultdict[
            type[Event],
            set[
                tuple[
                    EventHandler | weakref.ref[EventHandler],
                    EventSubscriptionOptions,
                ]
            ],
        ] = defaultdict(set)

        self._actions: list[Action] = []
        self._events: list[Event] = []

        self._event_handlers_queue = queue.Queue[
            tuple[EventHandler[Event], Event] | None
        ]()
        workers = [
            _SideEffectRunnerThread(self._event_handlers_queue)
            for _ in range(self.store_options.threads)
        ]
        for worker in workers:
            worker.start()

        self._is_running = Lock()

        self.subscribe_event(cast(type[Event], FinishEvent), self._handle_finish_event)

        if self.store_options.auto_init:
            if self.store_options.scheduler:
                self.store_options.scheduler(
                    lambda: self.dispatch(cast(Action, InitAction())),
                    interval=False,
                )
            else:
                self.dispatch(cast(Action, InitAction()))

        if self.store_options.scheduler:
            self.store_options.scheduler(self.run, interval=True)

    def _run_actions(self: Store[State, Action, Event]) -> None:
        action = self._actions.pop(0)
        result = self.reducer(self._state, action)
        if is_complete_reducer_result(result):
            self._state = result.state
            self.dispatch([*(result.actions or []), *(result.events or [])])
        elif is_state_reducer_result(result):
            self._state = result

        if isinstance(action, FinishAction):
            self.dispatch(cast(Event, FinishEvent()))

        if len(self._actions) == 0 and self._state:
            for listener_ in self._listeners.copy():
                if isinstance(listener_, weakref.ref):
                    listener = listener_()
                    if listener is None:
                        self._listeners.discard(listener_)
                        continue
                else:
                    listener = listener_
                listener(self._state)

    def _run_event_handlers(self: Store[State, Action, Event]) -> None:
        event = self._events.pop(0)
        for event_handler_, options in self._event_handlers[type(event)].copy():
            if isinstance(event_handler_, weakref.ref):
                event_handler = event_handler_()
                if event_handler is None:
                    self._event_handlers[type(event)].discard(
                        (event_handler_, options),
                    )
                    continue
            else:
                event_handler = event_handler_
            if options.run_async:
                self._event_handlers_queue.put((event_handler, event))
            elif len(signature(event_handler).parameters) == 1:
                cast(Callable[[Event], Any], event_handler)(event)
            else:
                cast(Callable[[], Any], event_handler)()

    def run(self: Store[State, Action, Event]) -> None:
        with self._is_running:
            while len(self._actions) > 0 or len(self._events) > 0:
                if len(self._actions) > 0:
                    self._run_actions()

                if len(self._events) > 0:
                    self._run_event_handlers()

    def dispatch(
        self: Store[State, Action, Event],
        *parameters: DispatchParameters[Action, Event],
        with_state: Callable[[State | None], DispatchParameters[Action, Event]]
        | None = None,
    ) -> None:
        if with_state is not None:
            self.dispatch(with_state(self._state))

        items = [
            item
            for items in parameters
            for item in (items if isinstance(items, list) else [items])
        ]

        for item in items:
            if isinstance(item, BaseAction):
                if self.store_options.action_middleware:
                    self.store_options.action_middleware(item)
                self._actions.append(item)
            if isinstance(item, BaseEvent):
                if self.store_options.event_middleware:
                    self.store_options.event_middleware(item)
                self._events.append(item)

        if self.store_options.scheduler is None and not self._is_running.locked():
            self.run()

    def subscribe(
        self: Store[State, Action, Event],
        listener: Callable[[State], Any],
        *,
        keep_ref: bool = True,
    ) -> Callable[[], None]:
        if keep_ref:
            listener_ref = listener
        elif isinstance(listener, MethodType):
            listener_ref = weakref.WeakMethod(listener)
        else:
            listener_ref = weakref.ref(listener)

        self._listeners.add(listener_ref)
        return lambda: self._listeners.remove(listener_ref)

    def subscribe_event(
        self: Store[State, Action, Event],
        event_type: type[Event2],
        handler: EventHandler[Event2],
        *,
        options: EventSubscriptionOptions | None = None,
    ) -> Callable[[], None]:
        subscription_options = (
            EventSubscriptionOptions() if options is None else options
        )

        if subscription_options.keep_ref:
            handler_ref = handler
        elif isinstance(handler, MethodType):
            handler_ref = weakref.WeakMethod(handler)
        else:
            handler_ref = weakref.ref(handler)

        self._event_handlers[cast(type[Event], event_type)].add(
            (handler_ref, subscription_options),
        )
        return lambda: self._event_handlers[cast(type[Event], event_type)].discard(
            (handler_ref, subscription_options),
        )

    def _handle_finish_event(
        self: Store[State, Action, Event],
        finish_event: Event,
    ) -> None:
        _ = finish_event
        for _ in range(self.store_options.threads):
            self._event_handlers_queue.put(None)

    def autorun(
        self: Store[State, Action, Event],
        selector: Callable[[State], SelectorOutput],
        comparator: Callable[[State], ComparatorOutput] | None = None,
        *,
        options: AutorunOptions[AutorunOriginalReturnType] | None = None,
    ) -> AutorunDecorator[
        State,
        SelectorOutput,
        AutorunOriginalReturnType,
    ]:
        def decorator(
            func: Callable[[SelectorOutput], AutorunOriginalReturnType]
            | Callable[[SelectorOutput, SelectorOutput], AutorunOriginalReturnType],
        ) -> AutorunReturnType[AutorunOriginalReturnType]:
            return Autorun(
                store=self,
                selector=selector,
                comparator=comparator,
                func=func,
                options=options or AutorunOptions(),
            )

        return decorator
