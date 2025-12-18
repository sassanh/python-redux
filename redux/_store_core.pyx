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
    StoreOptions,
    AutorunOptions,
    ViewOptions,
    CompleteReducerResult,
    is_state_reducer_result,
    NOT_SET,
)
from redux.utils import call_func, signature_without_selector
from immutable import is_immutable
from redux.serialization_mixin import SerializationMixin


cdef class AwaitableWrapper:
    """A wrapper for a coroutine to track if it has been awaited."""
    
    cdef object coro
    cdef tuple value

    def __init__(self, coro):
        self.coro = coro
        self.value = (False, None)

    def __await__(self):
        return self._wrap().__await__()

    async def _wrap(self):
        if self.value[0] is True:
            return self.value[1]
        self.value = (True, await self.coro)
        return self.value[1]

    def close(self):
        self.coro.close()

    @property
    def awaited(self):
        return self.value[0]

class SubscribeEventCleanup:
    def __init__(self, unsubscribe, handler):
        self.unsubscribe = unsubscribe
        self.handler = handler

    def __call__(self):
        return self.unsubscribe()
    
    def __repr__(self):
        return f'AwaitableWrapper({self.coro}, awaited={self.awaited})'
from libc.stdlib cimport malloc, free

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

            if result is not None and asyncio.iscoroutine(result) and task_creator is not None:
                task_creator(result)

    cpdef void _run_actions(self) except *:
        cdef object action
        cdef object result
        cdef bint has_work = len(self._actions) > 0
        
        while has_work:
            action = self._actions.pop(0)
            if action is not None:
                result = self.reducer(self._state, action)
                
                if isinstance(result, CompleteReducerResult):
                    self._state = result.state
                    self._call_listeners(self._state)
                    # Dispatch actions/events from result
                    if result.actions:
                        self._dispatch_list(result.actions)
                    if result.events:
                        self._dispatch_list(result.events)
                
                else:
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

        return SubscribeEventCleanup(unsubscribe, handler)

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
            
            # Mimic functools.wraps / standard decorator behavior
            if hasattr(func, '__name__'):
                wrapper.__name__ = func.__name__
            if hasattr(func, '__qualname__'):
                wrapper.__qualname__ = func.__qualname__
            if hasattr(func, '__doc__'):
                wrapper.__doc__ = func.__doc__
            if hasattr(func, '__module__'):
                wrapper.__module__ = func.__module__
            if hasattr(func, '__annotations__'):
                wrapper.__annotations__ = func.__annotations__
                
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
        return SerializationMixin.serialize_value.__func__(SerializationMixin, obj)

    @classmethod
    def _serialize_dataclass_to_dict(cls, obj):
        return SerializationMixin._serialize_dataclass_to_dict.__func__(SerializationMixin, obj)


cdef class Autorun:
    cdef object _store
    cdef object _selector
    cdef object _comparator
    cdef object _func
    cdef public object _options
    cdef public object _latest_value
    cdef object _last_selector_result
    cdef object _last_comparator_result
    cdef bint _should_be_called
    cdef object _subscriptions
    cdef public object _unsubscribe
    cdef public object _is_coroutine
    cdef dict __dict__
    cdef object __weakref__

    def __init__(
        self,
        *,
        store,
        selector,
        comparator,
        func,
        options,
    ):
        if hasattr(func, '__name__'):
            self.__name__ = f'Autorun:{func.__name__}'
        else:
            self.__name__ = f'Autorun:{func}'
        
        if hasattr(func, '__qualname__'):
            self.__qualname__ = f'Autorun:{func.__qualname__}'
        else:
            self.__qualname__ = f'Autorun:{func}'

        self.__signature__ = signature_without_selector(func)
        self.__module__ = func.__module__
        
        self.__annotations__ = getattr(func, '__annotations__', None)
        self.__defaults__ = getattr(func, '__defaults__', None)
        self.__kwdefaults__ = getattr(func, '__kwdefaults__', None)

        self._store = store
        self._selector = selector
        self._comparator = comparator
        self._should_be_called = False

        if options.keep_ref:
            self._func = func
        elif inspect.ismethod(func):
            self._func = weakref.WeakMethod(func, self.unsubscribe)
        else:
            self._func = weakref.ref(func, self.unsubscribe)
            
        self._is_coroutine = (
            asyncio.coroutines._is_coroutine
            if asyncio.iscoroutinefunction(func) and options.auto_await is False
            else None
        )
        self._options = options

        self._last_selector_result = NOT_SET
        # cast('ComparatorOutput', object()) equivalent
        self._last_comparator_result = object()

        if asyncio.iscoroutinefunction(func):
            # Hack for default value wrapper async
            # In Cython we can't easily define async def inside def
            # We'll just manually use the value
            default_value = options.default_value
            self._create_task_value(default_value)
            self._latest_value = default_value
        else:
            self._latest_value = options.default_value
            
        self._subscriptions = set()

        # Initial check
        # We need to call store.with_state...
        # But we can optimize this since we are inside Cython and have access to _store internals?
        # store.with_state returns a wrapper. calling it calls the func.
        # self.check needs to be called.
        
        # Original: store.with_state(lambda state: state, ignore_uninitialized_store=True)(self.check)()
        # Optimized: access store._state directly if possible or use public API
        
        cdef object state = store._state
        if state is not None or options.initial_call:
             if self.check(state) and self._options.initial_call:
                 self._should_be_called = False
                 self.call()

        if self._options.reactive:
            # We pass self.react which is a bound method
            self._unsubscribe = store._subscribe(self.react)
        else:
            self._unsubscribe = None

    cdef void _create_task_value(self, object value):
         # Helper to create a task returning value
         async def wrapper():
             return value
         if self._store.store_options.task_creator:
             self._store.store_options.task_creator(wrapper())

    def _create_task(self, coro):
        if self._store.store_options.task_creator:
            self._store.store_options.task_creator(coro)

    cpdef bint check(self, object state):
        if state is None:
            return False
        
        cdef object selector_result
        try:
            selector_result = self._selector(state)
        except AttributeError:
            return False
            
        cdef object comparator_result
        if self._comparator is None:
            comparator_result = selector_result
        else:
            try:
                comparator_result = self._comparator(state)
            except AttributeError:
                return False
        
        self._should_be_called = (
            self._should_be_called or comparator_result != self._last_comparator_result
        )
        self._last_selector_result = selector_result
        self._last_comparator_result = comparator_result
        return self._should_be_called

    def react(self, state):
        if self._options.reactive and self.check(state):
            self._should_be_called = False
            self.call()

    def unsubscribe(self, _=None):
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None

    def inform_subscribers(self):
        cdef object subscriber_
        cdef object subscriber
        
        for subscriber_ in list(self._subscriptions):
            if isinstance(subscriber_, weakref.ref):
                subscriber = subscriber_()
                if subscriber is None:
                    self._subscriptions.discard(subscriber_)
                    continue
            else:
                subscriber = subscriber_
            subscriber(self._latest_value)

    def call(self, *args, **kwargs):
        cdef object func
        cdef object value
        cdef object previous_value
        
        if isinstance(self._func, weakref.ref):
            func = self._func()
        else:
            func = self._func
            
        if func and self._last_selector_result is not NOT_SET:
            value = call_func(
                func,
                [self._last_selector_result],
                *args,
                **kwargs,
            )
            previous_value = self._latest_value
            
            if asyncio.iscoroutine(value):
                if self._options.auto_await is False:
                     if (
                         self._latest_value is not NOT_SET
                         and isinstance(self._latest_value, AwaitableWrapper)
                         and not self._latest_value.awaited
                     ):
                         self._latest_value.close()
                     self._latest_value = AwaitableWrapper(value)
                else:
                     self._latest_value = None
                     self._create_task(value)
            else:
                self._latest_value = value
                
            if self._latest_value is not previous_value:
                self.inform_subscribers()

    def __call__(self, *args, **kwargs):
        # Original: store.with_state(..., ignore_uninitialized_store=True)(self.check)()
        cdef object state = self._store._state
        # We manually call check with current state
        self.check(state)
        
        if self._should_be_called or args or kwargs or not self._options.memoization:
            self._should_be_called = False
            self.call(*args, **kwargs)
        
        return self._latest_value

    def __repr__(self):
        return (
            f'<{self.__class__.__name__} object at {id(self)}> '
            f'(func: {self._func}, last_value: {self._latest_value})'
        )

    @property
    def value(self):
        return self._latest_value

    def subscribe(self, callback, *, initial_run=None, keep_ref=None):
        if initial_run is None:
            initial_run = self._options.subscribers_initial_run
        if keep_ref is None:
            keep_ref = self._options.subscribers_keep_ref
            
        cdef object callback_ref
        if keep_ref:
            callback_ref = callback
        elif inspect.ismethod(callback):
            callback_ref = weakref.WeakMethod(callback)
        else:
            callback_ref = weakref.ref(callback)
            
        self._subscriptions.add(callback_ref)

        if initial_run:
            callback(self.value)

        def unsubscribe():
            self._subscriptions.discard(callback_ref)
        return unsubscribe

    def __get__(self, obj, owner):
        if obj is None:
            return self
        else:
            # Recreate partial equivalent
            # This is hard to fully replicate via partial in Cython for cdef class methods?
            # But the original code wraps the instance itself in partial(self, obj)
            # which works because Autorun is callable.
            # Cython classes are callable if __call__ is defined.
            import functools
            return functools.partial(self, obj)
