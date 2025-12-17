# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: nonecheck=False
# cython: cdivision=True

import asyncio
import inspect
import queue
import weakref
import dataclasses
from threading import Lock, Thread
from collections import defaultdict
from typing import Callable, Any, Iterable

from redux.basic_types import (
    BaseAction,
    BaseEvent,
    FinishAction,
    FinishEvent,
    InitAction,
    StoreOptions,
    AutorunOptions,
    ViewOptions,
    is_complete_reducer_result,
    is_state_reducer_result,
)
from redux.utils import call_func, signature_without_selector
from immutable import is_immutable
from redux.serialization_mixin import SerializationMixin

cdef class Store:
    """Cython-optimized Redux store."""
    
    # Public attributes
    cdef public object store_options
    cdef public object reducer
    
    # Private typed attributes
    cdef list _action_middlewares
    cdef list _event_middlewares
    cdef public object _state
    cdef set _listeners
    cdef object _event_handlers # defaultdict is a Python object
    cdef list _actions
    cdef list _events
    cdef object _event_handlers_queue
    cdef list _workers
    cdef object _is_running # Lock is a Python object

    @classmethod
    def __class_getitem__(cls, item):
        return cls

    def __init__(self, reducer, options=None):
        self.store_options = options or StoreOptions()
        self.reducer = reducer

        self._action_middlewares = list(self.store_options.action_middlewares)
        self._event_middlewares = list(self.store_options.event_middlewares)

        self._state = None
        self._listeners = set()
        self._event_handlers = defaultdict(set)

        self._actions = []
        self._events = []

        self._event_handlers_queue = queue.Queue()
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

    cpdef void _call_listeners(self, object state) except *:
        cdef object listener_ref
        cdef object listener
        cdef object result
        cdef object task_creator = self.store_options.task_creator

        # Create a copy to allow modification during iteration
        for listener_ref in list(self._listeners):
            if isinstance(listener_ref, weakref.ref):
                listener = listener_ref()
                if listener is None:
                    raise RuntimeError(
                        'Listener has been garbage collected. '
                        'Consider using `keep_ref=True` if it suits your use case.'
                    )
            else:
                listener = listener_ref

            result = listener(state)

            if asyncio.iscoroutine(result) and task_creator is not None:
                task_creator(result)

    cpdef void _run_actions(self) except *:
        cdef object action
        cdef object result
        cdef bint has_work = len(self._actions) > 0
        
        while has_work:
            action = self._actions.pop(0)
            if action is not None:
                result = self.reducer(self._state, action)
                
                if is_complete_reducer_result(result):
                    self._state = result.state
                    self._call_listeners(self._state)
                    # Dispatch actions/events from result
                    if result.actions:
                        self._dispatch_list(result.actions)
                    if result.events:
                        self._dispatch_list(result.events)
                
                elif is_state_reducer_result(result):
                    self._state = result
                    self._call_listeners(self._state)

                if isinstance(action, FinishAction):
                    self._dispatch_single(FinishEvent())
            
            has_work = len(self._actions) > 0

    cpdef void _run_event_handlers(self) except *:
        cdef object event
        cdef object event_type
        cdef object handlers
        
        while len(self._events) > 0:
            event = self._events.pop(0)
            if event is not None:
                if isinstance(event, FinishEvent):
                    self._handle_finish_event()
                
                event_type = type(event)
                handlers = self._event_handlers.get(event_type)
                if handlers:
                    for event_handler in list(handlers):
                        self._event_handlers_queue.put_nowait((event_handler, event))

    cpdef void run(self) except *:
        """Run the store."""
        with self._is_running:
            while len(self._actions) > 0 or len(self._events) > 0:
                if len(self._actions) > 0:
                    self._run_actions()
                if len(self._events) > 0:
                    self._run_event_handlers()

    cpdef void clean_up(self):
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

    cpdef void wait_for_event_handlers(self):
        """Wait for the event handlers to finish."""
        self._event_handlers_queue.join()

    def dispatch(self, *parameters, with_state=None):
        """Dispatch actions."""
        if with_state is not None:
            self.dispatch(with_state(self._state))
            # Note: The original code recursively calls dispatch, 
            # we do the same here.

        cdef list actions = []
        cdef object param
        
        for param in parameters:
            if isinstance(param, Iterable) and not isinstance(param, (str, bytes)):
                actions.extend(param)
            else:
                actions.append(param)
        
        self._dispatch_list(actions)

    cpdef void _dispatch(self, object items) except *:
        """Internal dispatch for Sequence of items."""
        # This matches the signature expected by Python code
        self._dispatch_list(list(items))

    # Optimization: Helper for list dispatch to avoid type checking overhead
    cdef void _dispatch_list(self, list items) except *:
        cdef object item
        cdef object action
        cdef object event
        cdef object processed
        cdef bint filtered
        
        for item in items:
            if isinstance(item, BaseAction):
                action = item
                filtered = False
                for action_middleware in self._action_middlewares:
                    processed = action_middleware(action)
                    if processed is None:
                        filtered = True
                        break
                    action = processed
                
                if not filtered:
                    self._actions.append(action)
            
            if isinstance(item, BaseEvent):
                event = item
                filtered = False
                for event_middleware in self._event_middlewares:
                    processed = event_middleware(event)
                    if processed is None:
                        filtered = True
                        break
                    event = processed
                
                if not filtered:
                    self._events.append(event)
        
        if self.store_options.scheduler is None and not self._is_running.locked():
            self.run()

    cdef void _dispatch_single(self, object item) except *:
        # Optimized for single item dispatch internal use
        self._dispatch_list([item])

    def _subscribe(self, listener, *, bint keep_ref=True):
        """Subscribe to state changes."""
        cdef object listener_ref

        def unsubscribe(_=None):
            try:
                self._listeners.remove(listener_ref)
            except KeyError:
                pass

        if keep_ref:
            listener_ref = listener
        elif inspect.ismethod(listener):
            listener_ref = weakref.WeakMethod(listener, unsubscribe)
        else:
            listener_ref = weakref.ref(listener, unsubscribe)

        self._listeners.add(listener_ref)
        return unsubscribe

    def subscribe_event(self, event_type, handler, *, bint keep_ref=True):
        """Subscribe to events."""
        cdef object handler_ref
        
        if keep_ref:
            handler_ref = handler
        elif inspect.ismethod(handler):
            handler_ref = weakref.WeakMethod(handler)
        else:
            handler_ref = weakref.ref(handler)

        # Cast event_type to ensure it's used as key
        self._event_handlers[event_type].add(handler_ref)

        def unsubscribe():
            try:
                self._event_handlers[event_type].discard(handler_ref)
            except KeyError:
                pass

        # Return object with unsubscribe method and handler attribute
        return type('SubscribeEventCleanup', (), {'unsubscribe': unsubscribe, 'handler': handler})

    def _wait_for_store_to_finish(self):
        """Wait for the store to finish."""
        import time
        while True:
            if (
                len(self._actions) == 0
                and len(self._events) == 0
                and self._event_handlers_queue.qsize() == 0
            ):
                time.sleep(self.store_options.grace_time_in_seconds)
                self.clean_up()
                if self.store_options.on_finish:
                    self.store_options.on_finish()
                break

    def _handle_finish_event(self):
        Thread(target=self._wait_for_store_to_finish).start()

    def autorun(self, selector, comparator=None, *, options=None):
        def autorun_decorator(func):
            return self.store_options.autorun_class(
                store=self,
                selector=selector,
                comparator=comparator,
                func=func,
                options=options or AutorunOptions(),
            )
        return autorun_decorator

    def view(self, selector, *, options=None):
        def view_decorator(func):
            _options = options or ViewOptions()
            return self.store_options.autorun_class(
                store=self,
                selector=selector,
                comparator=None,
                func=func,
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

    def with_state(self, selector, *, bint ignore_uninitialized_store=False):
        def with_state_decorator(func):
            def wrapper(*args, **kwargs):
                if self._state is None:
                    if ignore_uninitialized_store:
                        return None
                    raise RuntimeError('Store has not been initialized yet.')
                return call_func(func, [selector(self._state)], *args, **kwargs)

            signature = signature_without_selector(func)
            wrapper.__signature__ = signature
            return wrapper
        return with_state_decorator

    @property
    def snapshot(self):
        return self.serialize_value(self._state)

    def register_action_middleware(self, action_middleware):
        self._action_middlewares.append(action_middleware)

    def register_event_middleware(self, event_middleware):
        self._event_middlewares.append(event_middleware)

    def unregister_action_middleware(self, action_middleware):
        self._action_middlewares.remove(action_middleware)

    def unregister_event_middleware(self, event_middleware):
        self._event_middlewares.remove(event_middleware)

    # Delegate serialization to Python mixin to avoid Cython recursion depth segfaults
    # and preserve standard RecursionError behavior.
    @classmethod
    def serialize_value(cls, obj):
        return SerializationMixin.serialize_value.__func__(cls, obj)

    @classmethod
    def _serialize_dataclass_to_dict(cls, obj):
        return SerializationMixin._serialize_dataclass_to_dict.__func__(cls, obj)
