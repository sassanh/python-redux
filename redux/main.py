"""Redux store for managing state and side effects."""

from __future__ import annotations

import dataclasses
import inspect
import queue
import threading
import weakref
from asyncio import AbstractEventLoop, get_event_loop, iscoroutinefunction
from collections import defaultdict
from inspect import signature
from threading import Lock
from types import NoneType
from typing import Any, Callable, Coroutine, Generic, cast

from immutable import Immutable, is_immutable

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
    SnapshotAtom,
    State,
    is_complete_reducer_result,
    is_state_reducer_result,
)


class _SideEffectRunnerThread(threading.Thread, Generic[Event]):
    def __init__(
        self: _SideEffectRunnerThread[Event],
        *,
        task_queue: queue.Queue[tuple[EventHandler[Event], Event] | None],
        async_loop: AbstractEventLoop,
    ) -> None:
        super().__init__()
        self.task_queue = task_queue
        self.async_loop = async_loop

    def create_task(self: _SideEffectRunnerThread[Event], coro: Coroutine) -> None:
        self.async_loop.call_soon_threadsafe(lambda: self.async_loop.create_task(coro))

    def run(self: _SideEffectRunnerThread[Event]) -> None:
        while True:
            task = self.task_queue.get()
            if task is None:
                self.task_queue.task_done()
                break

            try:
                event_handler, event = task
                if len(signature(event_handler).parameters) == 1:
                    result = cast(Callable[[Event], Any], event_handler)(event)
                else:
                    result = cast(Callable[[], Any], event_handler)()
                if iscoroutinefunction(event_handler):
                    self.create_task(result)
            finally:
                self.task_queue.task_done()


class Store(Generic[State, Action, Event]):
    """Redux store for managing state and side effects."""

    def __init__(
        self: Store[State, Action, Event],
        reducer: ReducerType[State, Action, Event],
        options: CreateStoreOptions | None = None,
    ) -> None:
        """Create a new store."""
        self.store_options = options or CreateStoreOptions()
        self.reducer = reducer
        self._async_loop = self.store_options.async_loop or get_event_loop()

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
            _SideEffectRunnerThread(
                task_queue=self._event_handlers_queue,
                async_loop=self._async_loop,
            )
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
                result = listener(self._state)
                if iscoroutinefunction(listener):
                    self._async_loop.create_task(result)

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
            if not options.immediate_run:
                self._event_handlers_queue.put((event_handler, event))
            elif len(signature(event_handler).parameters) == 1:
                cast(Callable[[Event], Any], event_handler)(event)
            else:
                cast(Callable[[], Any], event_handler)()

    def run(self: Store[State, Action, Event]) -> None:
        """Run the store."""
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
        """Dispatch actions and/or events."""
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
        """Subscribe to state changes."""
        if keep_ref:
            listener_ref = listener
        elif inspect.ismethod(listener):
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
        """Subscribe to events."""
        subscription_options = (
            EventSubscriptionOptions() if options is None else options
        )

        if subscription_options.keep_ref:
            handler_ref = handler
        elif inspect.ismethod(handler):
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
        """Create a new autorun, reflecting on state changes."""

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

    @property
    def snapshot(self: Store[State, Action, Event]) -> SnapshotAtom:
        """Return a snapshot of the current state of the store."""
        return self.serialize_value(self._state)

    @classmethod
    def serialize_value(cls: type[Store], obj: object | type) -> SnapshotAtom:
        """Serialize a value to a snapshot atom."""
        if isinstance(obj, (int, float, str, bool, NoneType)):
            return obj
        if callable(obj):
            return cls.serialize_value(obj())
        if isinstance(obj, (list, tuple)):
            return [cls.serialize_value(i) for i in obj]
        if is_immutable(obj):
            return cls._serialize_dataclass_to_dict(obj)
        msg = f'Unable to serialize object with type `{type(obj)}`.'
        raise TypeError(msg)

    @classmethod
    def _serialize_dataclass_to_dict(
        cls: type[Store],
        obj: Immutable,
    ) -> dict[str, Any]:
        result = {}
        for field in dataclasses.fields(obj):
            value = cls.serialize_value(getattr(obj, field.name))
            result[field.name] = value
        return result
