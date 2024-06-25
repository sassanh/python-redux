"""Redux store for managing state and side effects."""

from __future__ import annotations

import asyncio
import inspect
import queue
import weakref
from collections import defaultdict
from threading import Lock, Thread
from typing import (
    Any,
    Awaitable,
    Callable,
    Concatenate,
    Generic,
    cast,
    overload,
)

from redux.autorun import Autorun
from redux.basic_types import (
    Action,
    ActionMiddleware,
    AutorunArgs,
    AutorunDecorator,
    AutorunOptions,
    AutorunOptionsWithDefault,
    AutorunOptionsWithoutDefault,
    AutorunOriginalReturnType,
    AutorunReturnType,
    AwaitableOrNot,
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
    UnknownAutorunDecorator,
    UnknownViewDecorator,
    ViewArgs,
    ViewDecorator,
    ViewOptions,
    ViewOptionsWithDefault,
    ViewOptionsWithoutDefault,
    ViewOriginalReturnType,
    ViewReturnType,
    is_complete_reducer_result,
    is_state_reducer_result,
)
from redux.serialization_mixin import SerializationMixin
from redux.side_effect_runner import SideEffectRunnerThread


class Store(Generic[State, Action, Event], SerializationMixin):
    """Redux store for managing state and side effects."""

    def __init__(
        self: Store,
        reducer: ReducerType[State, Action, Event],
        options: CreateStoreOptions[Action, Event] | None = None,
    ) -> None:
        """Create a new store."""
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
        while len(self._actions) > 0:
            action = self._actions.pop(0)
            if action is not None:
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
        while len(self._events) > 0:
            event = self._events.pop(0)
            if event is not None:
                for event_handler in self._event_handlers[type(event)].copy():
                    self._event_handlers_queue.put_nowait((event_handler, event))

    def run(self: Store[State, Action, Event]) -> None:
        """Run the store."""
        with self._is_running:
            while len(self._actions) > 0 or len(self._events) > 0:
                if len(self._actions) > 0:
                    self._run_actions()

                if len(self._events) > 0:
                    self._run_event_handlers()

    def clean_up(self: Store[State, Action, Event]) -> None:
        """Clean up the store."""
        self._event_handlers_queue.join()
        for _ in range(self.store_options.threads):
            self._event_handlers_queue.put_nowait(None)
        self._event_handlers_queue.join()
        for worker in self._workers:
            worker.join()
        self._workers.clear()
        self._listeners.clear()
        self._event_handlers.clear()

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
                    action_ = action_middleware(action)
                    if action_ is None:
                        break
                    action = action_
                else:
                    self._actions.append(action)
            if isinstance(item, BaseEvent):
                event = cast(Event, item)
                for event_middleware in self._event_middlewares:
                    event_ = event_middleware(event)
                    if event_ is None:
                        break
                    event = event_
                else:
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

    def wait_for_store_to_finish(self: Store[State, Action, Event]) -> None:
        """Wait for the store to finish."""
        import time

        while True:
            if (
                self._actions == []
                and self._events == []
                and self._event_handlers_queue.qsize() == 0
            ):
                time.sleep(self.store_options.grace_time_in_seconds)
                self.clean_up()
                if self.store_options.on_finish:
                    self.store_options.on_finish()
                break
            time.sleep(0.1)

    def _handle_finish_event(self: Store[State, Action, Event]) -> None:
        Thread(target=self.wait_for_store_to_finish).start()

    @overload
    def autorun(
        self: Store[State, Action, Event],
        selector: Callable[[State], SelectorOutput],
        comparator: Callable[[State], ComparatorOutput] | None = None,
        *,
        options: AutorunOptionsWithoutDefault | None = None,
    ) -> UnknownAutorunDecorator[SelectorOutput]: ...
    @overload
    def autorun(
        self: Store[State, Action, Event],
        selector: Callable[[State], SelectorOutput],
        comparator: Callable[[State], ComparatorOutput] | None = None,
        *,
        options: AutorunOptionsWithDefault[AutorunOriginalReturnType],
    ) -> AutorunDecorator[SelectorOutput, AutorunOriginalReturnType]: ...
    def autorun(
        self: Store[State, Action, Event],
        selector: Callable[[State], SelectorOutput],
        comparator: Callable[[State], ComparatorOutput] | None = None,
        *,
        options: AutorunOptions[AutorunOriginalReturnType] | None = None,
    ) -> (
        AutorunDecorator[SelectorOutput, AutorunOriginalReturnType]
        | UnknownAutorunDecorator[SelectorOutput]
    ):
        """Create a new autorun, reflecting on state changes."""

        @overload
        def decorator(
            func: Callable[
                Concatenate[SelectorOutput, AutorunArgs],
                AutorunOriginalReturnType,
            ],
        ) -> AutorunReturnType[AutorunOriginalReturnType, AutorunArgs]: ...
        @overload
        def decorator(
            func: Callable[
                Concatenate[SelectorOutput, AutorunArgs],
                Awaitable[AutorunOriginalReturnType],
            ],
        ) -> AutorunReturnType[Awaitable[AutorunOriginalReturnType], AutorunArgs]: ...
        def decorator(
            func: Callable[
                Concatenate[SelectorOutput, AutorunArgs],
                AwaitableOrNot[AutorunOriginalReturnType],
            ],
        ) -> AutorunReturnType[AwaitableOrNot[AutorunOriginalReturnType], AutorunArgs]:
            return Autorun(
                store=self,
                selector=selector,
                comparator=comparator,
                func=cast(Callable, func),
                options=options or AutorunOptions(),
            )

        return decorator

    @overload
    def view(
        self: Store[State, Action, Event],
        selector: Callable[[State], SelectorOutput],
        *,
        options: ViewOptionsWithoutDefault | None = None,
    ) -> UnknownViewDecorator[SelectorOutput]: ...
    @overload
    def view(
        self: Store[State, Action, Event],
        selector: Callable[[State], SelectorOutput],
        *,
        options: ViewOptionsWithDefault[ViewOriginalReturnType],
    ) -> ViewDecorator[SelectorOutput, ViewOriginalReturnType]: ...
    def view(
        self: Store[State, Action, Event],
        selector: Callable[[State], SelectorOutput],
        *,
        options: ViewOptions[ViewOriginalReturnType] | None = None,
    ) -> (
        ViewDecorator[SelectorOutput, ViewOriginalReturnType]
        | UnknownViewDecorator[SelectorOutput]
    ):
        """Create a new view, throttling calls for unchanged selector results."""

        @overload
        def decorator(
            func: Callable[
                Concatenate[SelectorOutput, ViewArgs],
                ViewOriginalReturnType,
            ],
        ) -> ViewReturnType[ViewOriginalReturnType, ViewArgs]: ...
        @overload
        def decorator(
            func: Callable[
                Concatenate[SelectorOutput, ViewArgs],
                Awaitable[ViewOriginalReturnType],
            ],
        ) -> ViewReturnType[Awaitable[ViewOriginalReturnType], ViewArgs]: ...

        def decorator(
            func: Callable[
                Concatenate[SelectorOutput, ViewArgs],
                AwaitableOrNot[ViewOriginalReturnType],
            ],
        ) -> ViewReturnType[AwaitableOrNot[ViewOriginalReturnType], ViewArgs]:
            _options = options or ViewOptions()
            return Autorun(
                store=self,
                selector=selector,
                comparator=None,
                func=cast(Callable, func),
                options=AutorunOptions(
                    default_value=_options.default_value,
                    initial_call=False,
                    auto_call=False,
                    reactive=False,
                    keep_ref=_options.keep_ref,
                    subscribers_initial_run=_options.subscribers_initial_run,
                    subscribers_keep_ref=_options.subscribers_keep_ref,
                ),
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
