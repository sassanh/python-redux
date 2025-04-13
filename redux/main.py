"""Redux store for managing state and side effects."""

from __future__ import annotations

import asyncio
import inspect
import queue
import weakref
from collections import defaultdict
from functools import wraps
from threading import Lock, Thread
from typing import (
    TYPE_CHECKING,
    Any,
    Concatenate,
    Generic,
    cast,
    overload,
)

from redux.basic_types import (
    Action,
    ActionMiddleware,
    Args,
    AutoAwait,
    AutorunDecorator,
    AutorunOptions,
    AutorunOptionsType,
    AutorunReturnType,
    AwaitableOrNot,
    BaseAction,
    BaseEvent,
    ComparatorOutput,
    DispatchParameters,
    Event,
    EventHandler,
    EventMiddleware,
    FinishAction,
    FinishEvent,
    InitAction,
    ReducerType,
    ReturnType,
    SelectorOutput,
    SnapshotAtom,
    State,
    StoreOptions,
    StrictEvent,
    SubscribeEventCleanup,
    ViewDecorator,
    ViewOptions,
    ViewReturnType,
    WithStateDecorator,
    is_complete_reducer_result,
    is_state_reducer_result,
)
from redux.serialization_mixin import SerializationMixin

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


class Store(Generic[State, Action, Event], SerializationMixin):
    """Redux store for managing state and side effects."""

    def __init__(
        self,
        reducer: ReducerType[State, Action, Event],
        options: StoreOptions[Action, Event] | None = None,
    ) -> None:
        """Create a new store."""
        self.store_options = options or StoreOptions()
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
            self.store_options.side_effect_runner_class(
                task_queue=self._event_handlers_queue,
                create_task=self._create_task,
            )
            for _ in range(self.store_options.side_effect_threads)
        ]
        for worker in self._workers:
            worker.start()

        self._is_running = Lock()

        if self.store_options.auto_init:
            if self.store_options.scheduler:
                self.store_options.scheduler(
                    lambda: self.dispatch(cast('Action', InitAction())),
                    interval=False,
                )
            else:
                self.dispatch(cast('Action', InitAction()))

        if self.store_options.scheduler:
            self.store_options.scheduler(self.run, interval=True)

    def _call_listeners(self: Store[State, Action, Event], state: State) -> None:
        for listener_ in self._listeners.copy():
            if isinstance(listener_, weakref.ref):
                listener = listener_()
                assert listener is not None  # noqa: S101
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
                    self._dispatch([*(result.actions or []), *(result.events or [])])
                elif is_state_reducer_result(result):
                    self._state = result
                    self._call_listeners(self._state)

                if isinstance(action, FinishAction):
                    self._dispatch([cast('Event', FinishEvent())])

    def _run_event_handlers(self: Store[State, Action, Event]) -> None:
        while len(self._events) > 0:
            event = self._events.pop(0)
            if event is not None:
                if isinstance(event, FinishEvent):
                    self._handle_finish_event()
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
        self.wait_for_event_handlers()
        for _ in range(self.store_options.side_effect_threads):
            self._event_handlers_queue.put_nowait(None)
        self.wait_for_event_handlers()
        for worker in self._workers:
            worker.join()
        self._workers.clear()
        self._listeners.clear()
        self._event_handlers.clear()

    def wait_for_event_handlers(self: Store[State, Action, Event]) -> None:
        """Wait for the event handlers to finish."""
        self._event_handlers_queue.join()

    @overload
    def dispatch(
        self: Store[State, Action, Event],
        *parameters: DispatchParameters[Action],
    ) -> None: ...
    @overload
    def dispatch(
        self: Store[State, Action, Event],
        *,
        with_state: Callable[[State | None], DispatchParameters[Action]] | None = None,
    ) -> None: ...
    def dispatch(
        self: Store[State, Action, Event],
        *parameters: DispatchParameters[Action],
        with_state: Callable[[State | None], DispatchParameters[Action]] | None = None,
    ) -> None:
        """Dispatch actions."""
        if with_state is not None:
            self.dispatch(with_state(self._state))

        actions = [
            action
            for actions in parameters
            for action in (actions if isinstance(actions, list) else [actions])
        ]
        self._dispatch(actions)

    def _dispatch(
        self: Store[State, Action, Event],
        items: list[Action | Event],
    ) -> None:
        for item in items:
            if isinstance(item, BaseAction):
                action = cast('Action', item)
                for action_middleware in self._action_middlewares:
                    action_ = action_middleware(action)
                    if action_ is None:
                        break
                    action = action_
                else:
                    self._actions.append(action)
            if isinstance(item, BaseEvent):
                event = cast('Event', item)
                for event_middleware in self._event_middlewares:
                    event_ = event_middleware(event)
                    if event_ is None:
                        break
                    event = event_
                else:
                    self._events.append(event)

        if self.store_options.scheduler is None and not self._is_running.locked():
            self.run()

    def _subscribe(
        self: Store[State, Action, Event],
        listener: Callable[[State], Any],
        *,
        keep_ref: bool = True,
    ) -> Callable[[], None]:
        """Subscribe to state changes."""

        def unsubscribe(_: weakref.ref | None = None) -> None:
            return self._listeners.remove(listener_ref)

        if keep_ref:
            listener_ref = listener
        elif inspect.ismethod(listener):
            listener_ref = weakref.WeakMethod(listener, unsubscribe)
        else:
            listener_ref = weakref.ref(listener, unsubscribe)

        self._listeners.add(listener_ref)

        return unsubscribe

    def subscribe_event(
        self: Store[State, Action, Event],
        event_type: type[StrictEvent],
        handler: EventHandler[StrictEvent],
        *,
        keep_ref: bool = True,
    ) -> SubscribeEventCleanup:
        """Subscribe to events."""
        if keep_ref:
            handler_ref = handler
        elif inspect.ismethod(handler):
            handler_ref = weakref.WeakMethod(handler)
        else:
            handler_ref = weakref.ref(handler)

        self._event_handlers[cast('Any', event_type)].add(handler_ref)

        def unsubscribe() -> None:
            self._event_handlers[cast('Any', event_type)].discard(handler_ref)

        return SubscribeEventCleanup(unsubscribe=unsubscribe, handler=handler)

    def _wait_for_store_to_finish(self: Store[State, Action, Event]) -> None:
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

    def _handle_finish_event(self: Store[State, Action, Event]) -> None:
        Thread(target=self._wait_for_store_to_finish).start()

    def autorun(
        self: Store[State, Action, Event],
        selector: Callable[[State], SelectorOutput],
        comparator: Callable[[State], ComparatorOutput] | None = None,
        *,
        options: AutorunOptionsType[ReturnType, AutoAwait] | None = None,
    ) -> AutorunDecorator[ReturnType, SelectorOutput, AutoAwait]:
        """Create a new autorun, reflecting on state changes."""

        def autorun_decorator(
            func: Callable[
                Concatenate[SelectorOutput, Args],
                ReturnType,
            ],
        ) -> AutorunReturnType[ReturnType | None, Args]:
            return self.store_options.autorun_class(
                store=self,
                selector=selector,
                comparator=comparator,
                func=cast('Callable', func),
                options=options or AutorunOptions(),
            )

        return cast('AutorunDecorator', autorun_decorator)

    def view(
        self: Store[State, Action, Event],
        selector: Callable[[State], SelectorOutput],
        *,
        options: ViewOptions[ReturnType] | None = None,
    ) -> ViewDecorator[ReturnType, SelectorOutput]:
        """Create a new view, throttling calls for unchanged selector results."""

        @overload
        def view_decorator(
            func: Callable[
                Concatenate[SelectorOutput, Args],
                ReturnType,
            ],
        ) -> ViewReturnType[ReturnType, Args]: ...
        @overload
        def view_decorator(
            func: Callable[
                Concatenate[SelectorOutput, Args],
                Awaitable[ReturnType],
            ],
        ) -> ViewReturnType[Awaitable[ReturnType], Args]: ...

        def view_decorator(
            func: Callable[
                Concatenate[SelectorOutput, Args],
                AwaitableOrNot[ReturnType],
            ],
        ) -> ViewReturnType[AwaitableOrNot[ReturnType], Args]:
            _options = options or ViewOptions()
            return self.store_options.autorun_class(
                store=self,
                selector=selector,
                comparator=None,
                func=cast('Callable', func),
                options=AutorunOptions(
                    default_value=_options.default_value,
                    auto_await=False,
                    initial_call=False,
                    reactive=False,
                    memoization=_options.memoization,
                    keep_ref=_options.keep_ref,
                    subscribers_initial_run=_options.subscribers_initial_run,
                    subscribers_keep_ref=_options.subscribers_keep_ref,
                ),
            )

        return view_decorator

    def with_state(
        self: Store[State, Action, Event],
        selector: Callable[[State], SelectorOutput],
    ) -> WithStateDecorator[SelectorOutput]:
        """Wrap a function, passing the result of the selector as its first argument.

        Note that it has zero reactivity, it just runs the function with the result
        of the selector whenever it is called explicitly. To make it reactive, use
        `autorun` instead.

        This is mostly for improving code oragnization and readability. Directly Using
        `store._state` is also possible.
        """

        def with_state_decorator(
            func: Callable[
                Concatenate[SelectorOutput, Args],
                ReturnType,
            ],
        ) -> Callable[Args, ReturnType]:
            def wrapper(*args: Args.args, **kwargs: Args.kwargs) -> ReturnType:
                if self._state is None:
                    msg = 'Store has not been initialized yet.'
                    raise RuntimeError(msg)
                return func(selector(self._state), *args, **kwargs)

            signature = inspect.signature(func)
            parameters = list(signature.parameters.values())
            if parameters and parameters[0].kind in [
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            ]:
                parameters = parameters[1:]

            wrapped = wraps(func)(wrapper)
            wrapped.__signature__ = signature.replace(  # pyright: ignore [reportAttributeAccessIssue]
                parameters=parameters,
            )

            return wrapped

        return with_state_decorator

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
