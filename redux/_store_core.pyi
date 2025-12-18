


import inspect
import queue
import weakref
from collections import defaultdict
from collections.abc import Awaitable, Iterable, Sequence
from functools import wraps
from threading import Lock
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
    FinishEvent,
    InitAction,
    MethodSelf,
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
)
from redux.serialization_mixin import SerializationMixin
from redux.utils import call_func, signature_without_selector

if TYPE_CHECKING:
    from collections.abc import Callable


class Store(SerializationMixin, Generic[State, Action, Event]):


    def __init__(
        self,
        reducer: ReducerType[State, Action | InitAction, Event | None],
        options: StoreOptions[Action, Event] | None = None,
    ) -> None:

        self.store_options = options or StoreOptions()
        self.reducer = reducer

        self._action_middlewares = list(self.store_options.action_middlewares)
        self._event_middlewares = list(self.store_options.event_middlewares)

        self._state: State | None = None
        self._listeners: set[
            Callable[[State], AwaitableOrNot[None]]
            | weakref.ref[Callable[[State], AwaitableOrNot[None]]]
        ] = set()
        self._event_handlers: defaultdict[
            type[Event | FinishEvent],
            set[EventHandler | weakref.ref[EventHandler]],
        ] = defaultdict(set)

        self._actions: list[Action | InitAction] = []
        self._events: list[Event | FinishEvent] = []

        self._event_handlers_queue = queue.Queue[
            tuple[EventHandler[Event | FinishEvent], Event | FinishEvent] | None
        ]()
        self._workers = [
            self.store_options.side_effect_runner_class(
                task_queue=self._event_handlers_queue,
                create_task=self.store_options.task_creator,
            )
            for _ in range(self.store_options.side_effect_threads)
        ]
        for worker in self._workers:
            worker.start()

        self._is_running = Lock()

        if self.store_options.auto_init:
            if self.store_options.scheduler:
                self.store_options.scheduler(
                    lambda: self.dispatch(InitAction()),
                    interval=False,
                )
            else:
                self.dispatch(InitAction())

        if self.store_options.scheduler:
            self.store_options.scheduler(self.run, interval=True)

    def _call_listeners(self: Store[State, Action, Event], state: State) -> None:
        ...

    def _run_actions(self: Store[State, Action, Event]) -> None:
        ...

    def _run_event_handlers(self: Store[State, Action, Event]) -> None:
        ...

    def run(self: Store[State, Action, Event]) -> None:

        ...

    def clean_up(self: Store[State, Action, Event]) -> None:

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

        ...

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

        if with_state is not None:
            self.dispatch(with_state(self._state))

        actions = [
            action
            for actions in parameters
            for action in (actions if isinstance(actions, Iterable) else [actions])
        ]
        self._dispatch(actions)

    def _dispatch(
        self: Store[State, Action, Event],
        items: Sequence[Action | Event | InitAction | FinishEvent | None],
    ) -> None:
        for item in items:
            if isinstance(item, BaseAction):
                action = item
                for action_middleware in self._action_middlewares:
                    action_ = action_middleware(action)
                    if action_ is None:
                        break
                    action = action_
                else:
                    self._actions.append(action)
            if isinstance(item, BaseEvent):
                event = item
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


        def unsubscribe(_: weakref.ref | None = None) -> None:
            ...

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

        if keep_ref:
            handler_ref = handler
        elif inspect.ismethod(handler):
            handler_ref = weakref.WeakMethod(handler)
        else:
            handler_ref = weakref.ref(handler)

        self._event_handlers[cast(Event, event_type)].add(handler_ref)

        def unsubscribe() -> None:
            ...

        return SubscribeEventCleanup(unsubscribe=unsubscribe, handler=handler)

    def _wait_for_store_to_finish(self: Store[State, Action, Event]) -> None:

        ...

    def _handle_finish_event(self: Store[State, Action, Event]) -> None:
        ...

    def autorun(
        self: Store[State, Action, Event],
        selector: Callable[[State], SelectorOutput],
        comparator: Callable[[State], ComparatorOutput] | None = None,
        *,
        options: AutorunOptionsType[ReturnType, AutoAwait] | None = None,
    ) -> AutorunDecorator[ReturnType, SelectorOutput, AutoAwait]:


        def autorun_decorator(
            func: Callable[
                Concatenate[SelectorOutput, Args],
                AwaitableOrNot[ReturnType],
            ],
        ) -> AutorunReturnType[Args, ReturnType]:
            ...

        return cast(AutorunDecorator, autorun_decorator)

    def view(
        self: Store[State, Action, Event],
        selector: Callable[[State], SelectorOutput],
        *,
        options: ViewOptions[ReturnType] | None = None,
    ) -> ViewDecorator[ReturnType, SelectorOutput]:


        @overload
        def view_decorator(
            func: Callable[
                Concatenate[SelectorOutput, Args],
                ReturnType,
            ]
            | Callable[
                Concatenate[MethodSelf, SelectorOutput, Args],
                ReturnType,
            ],
        ) -> ViewReturnType[ReturnType, Args]: ...
        @overload
        def view_decorator(
            func: Callable[
                Concatenate[SelectorOutput, Args],
                Awaitable[ReturnType],
            ]
            | Callable[
                Concatenate[MethodSelf, SelectorOutput, Args],
                Awaitable[ReturnType],
            ],
        ) -> ViewReturnType[Awaitable[ReturnType], Args]: ...
        def view_decorator(
            func: Callable[
                Concatenate[SelectorOutput, Args],
                AwaitableOrNot[ReturnType],
            ]
            | Callable[
                Concatenate[MethodSelf, SelectorOutput, Args],
                AwaitableOrNot[ReturnType],
            ],
        ) -> ViewReturnType[AwaitableOrNot[ReturnType], Args]:
            _options = options or ViewOptions()
            return self.store_options.autorun_class(
                store=self,
                selector=selector,
                comparator=None,
                func=cast(Callable, func),
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
        *,
        ignore_uninitialized_store: bool = False,
    ) -> WithStateDecorator[SelectorOutput]:


        @overload
        def with_state_decorator(
            func: Callable[
                Concatenate[SelectorOutput, Args],
                ReturnType,
            ],
        ) -> Callable[Args, ReturnType]: ...
        @overload
        def with_state_decorator(
            func: Callable[
                Concatenate[MethodSelf, SelectorOutput, Args],
                ReturnType,
            ],
        ) -> Callable[Concatenate[MethodSelf, Args], ReturnType]: ...
        def with_state_decorator(
            func: Callable[
                Concatenate[SelectorOutput, Args],
                ReturnType,
            ]
            | Callable[
                Concatenate[MethodSelf, SelectorOutput, Args],
                ReturnType,
            ],
        ) -> (
            Callable[Args, ReturnType]
            | Callable[Concatenate[MethodSelf, Args], ReturnType]
        ):
            def wrapper(*args: Args.args, **kwargs: Args.kwargs) -> ReturnType:
                if self._state is None:
                    if ignore_uninitialized_store:
                        return cast(ReturnType, None)
                    msg = 'Store has not been initialized yet.'
                    raise RuntimeError(msg)
                return call_func(func, [selector(self._state)], *args, **kwargs)

            signature = signature_without_selector(func)
            wrapped = wraps(cast(Any, func))(wrapper)
            wrapped.__signature__ = signature  # pyright: ignore [reportAttributeAccessIssue]

            return wrapped

        return with_state_decorator

    @property
    def snapshot(self: Store[State, Action, Event]) -> SnapshotAtom:

        ...

    def register_action_middleware(
        self: Store[State, Action, Event],
        action_middleware: ActionMiddleware,
    ) -> None:

        ...

    def register_event_middleware(
        self: Store[State, Action, Event],
        event_middleware: EventMiddleware,
    ) -> None:

        ...

    def unregister_action_middleware(
        self: Store[State, Action, Event],
        action_middleware: ActionMiddleware,
    ) -> None:

        ...

    def unregister_event_middleware(
        self: Store[State, Action, Event],
        event_middleware: EventMiddleware,
    ) -> None:

        ...
