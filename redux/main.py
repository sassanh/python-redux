"""Redux store for managing state and side effects."""

from __future__ import annotations

import asyncio
import inspect
import queue
import weakref
from collections import defaultdict
from threading import Lock
from typing import Any, Callable, Generic, cast

from redux.autorun import Autorun
from redux.basic_types import (
    Action,
    ActionMiddleware,
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
    EventMiddleware,
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
from redux.serialization_mixin import SerializationMixin
from redux.side_effect_runner import SideEffectRunnerThread


class Store(Generic[State, Action, Event], SerializationMixin):
    """Redux store for managing state and side effects."""

    def __init__(
        self: Store[State, Action, Event],
        reducer: ReducerType[State, Action, Event],
        options: CreateStoreOptions[Action, Event] | None = None,
    ) -> None:
        """Create a new store."""
        self.finished = False
        self.store_options = options or CreateStoreOptions()
        self.reducer = reducer
        self._create_task = self.store_options.task_creator

        self._action_middlewares = list(self.store_options.action_middlewares)
        self._event_middlewares = list(self.store_options.event_middlewares)

        self._state: State | None = None
        self._listeners: set[
            Callable[[State], Any] | weakref.ref[Callable[[State], Any]]
        ] = set()
        self._event_handlers: defaultdict[
            type[Event],
            set[EventHandler | weakref.ref[EventHandler]],
        ] = defaultdict(set)

        self._actions: list[Action] = []
        self._events: list[Event] = []

        self._event_handlers_queue = queue.Queue[
            tuple[EventHandler[Event], Event] | None
        ]()
        self._workers = [
            SideEffectRunnerThread(task_queue=self._event_handlers_queue)
            for _ in range(self.store_options.threads)
        ]
        for worker in self._workers:
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

    def _call_listeners(self: Store[State, Action, Event], state: State) -> None:
        for listener_ in self._listeners.copy():
            if isinstance(listener_, weakref.ref):
                listener = listener_()
                if listener is None:
                    self._listeners.discard(listener_)
                    continue
            else:
                listener = listener_
            result = listener(state)
            if asyncio.iscoroutine(result) and self._create_task:
                self._create_task(result)

    def _run_actions(self: Store[State, Action, Event]) -> None:
        action = self._actions.pop(0)
        result = self.reducer(self._state, action)
        if is_complete_reducer_result(result):
            self._state = result.state
            self._call_listeners(self._state)
            self.dispatch([*(result.actions or []), *(result.events or [])])
        elif is_state_reducer_result(result):
            self._state = result
            self._call_listeners(self._state)

        if isinstance(action, FinishAction):
            self.dispatch(cast(Event, FinishEvent()))

    def _run_event_handlers(self: Store[State, Action, Event]) -> None:
        event = self._events.pop(0)
        for event_handler_ in self._event_handlers[type(event)].copy():
            self._event_handlers_queue.put_nowait((event_handler_, event))

    def run(self: Store[State, Action, Event]) -> None:
        """Run the store."""
        with self._is_running:
            while len(self._actions) > 0 or len(self._events) > 0:
                if len(self._actions) > 0:
                    self._run_actions()

                if len(self._events) > 0:
                    self._run_event_handlers()
        if (
            self.finished
            and self._actions == []
            and self._events == []
            and not any(worker.is_alive() for worker in self._workers)
        ):
            self.clean_up()

    def clean_up(self: Store[State, Action, Event]) -> None:
        """Clean up the store."""
        for worker in self._workers:
            worker.join()
        self._workers.clear()
        self._listeners.clear()
        self._event_handlers.clear()
        if self.store_options.on_finish:
            self.store_options.on_finish()

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
                action = cast(Action, item)
                for action_middleware in self._action_middlewares:
                    action = action_middleware(action)
                self._actions.append(action)
            if isinstance(item, BaseEvent):
                event = cast(Event, item)
                for event_middleware in self._event_middlewares:
                    event = event_middleware(event)
                self._events.append(event)

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
        keep_ref: bool = True,
    ) -> Callable[[], None]:
        """Subscribe to events."""
        if keep_ref:
            handler_ref = handler
        elif inspect.ismethod(handler):
            handler_ref = weakref.WeakMethod(handler)
        else:
            handler_ref = weakref.ref(handler)

        self._event_handlers[cast(type[Event], event_type)].add(handler_ref)

        def unsubscribe() -> None:
            self._event_handlers[cast(type[Event], event_type)].discard(handler_ref)

        return unsubscribe

    def _handle_finish_event(self: Store[State, Action, Event]) -> None:
        for _ in range(self.store_options.threads):
            self._event_handlers_queue.put_nowait(None)
        self.finished = True

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

    def register_action_middleware(
        self: Store[State, Action, Event],
        action_middleware: ActionMiddleware,
    ) -> None:
        """Register an action dispatch middleware."""
        self._action_middlewares.append(action_middleware)

    def register_event_middleware(
        self: Store[State, Action, Event],
        event_middleware: EventMiddleware,
    ) -> None:
        """Register an action dispatch middleware."""
        self._event_middlewares.append(event_middleware)

    def unregister_action_middleware(
        self: Store[State, Action, Event],
        action_middleware: ActionMiddleware,
    ) -> None:
        """Unregister an action dispatch middleware."""
        self._action_middlewares.remove(action_middleware)

    def unregister_event_middleware(
        self: Store[State, Action, Event],
        event_middleware: EventMiddleware,
    ) -> None:
        """Unregister an action dispatch middleware."""
        self._event_middlewares.remove(event_middleware)
