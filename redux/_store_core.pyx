# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
"""Cython-optimized core Store operations for python-redux."""

from cpython.ref cimport PyObject
from libc.stdint cimport int64_t
import asyncio
import weakref


cdef class FastActionQueue:
    """Optimized action queue for dispatch operations."""

    cdef list _actions
    cdef list _events

    def __cinit__(self):
        self._actions = []
        self._events = []

    cpdef void append_action(self, object action):
        """Add an action to the queue."""
        self._actions.append(action)

    cpdef void append_event(self, object event):
        """Add an event to the queue."""
        self._events.append(event)

    cpdef object pop_action(self):
        """Remove and return the first action, or None if empty."""
        if self._actions:
            return self._actions.pop(0)
        return None

    cpdef object pop_event(self):
        """Remove and return the first event, or None if empty."""
        if self._events:
            return self._events.pop(0)
        return None

    cpdef bint has_actions(self):
        """Check if there are pending actions."""
        return len(self._actions) > 0

    cpdef bint has_events(self):
        """Check if there are pending events."""
        return len(self._events) > 0

    cpdef int action_count(self):
        """Return the number of pending actions."""
        return len(self._actions)

    cpdef int event_count(self):
        """Return the number of pending events."""
        return len(self._events)

    cpdef void clear(self):
        """Clear all queues."""
        self._actions.clear()
        self._events.clear()


cpdef void call_listeners_fast(set listeners, object state, object task_creator) except *:
    """
    Optimized listener notification.

    Args:
        listeners: Set of listener callables or weak references
        state: Current state to pass to listeners
        task_creator: Optional coroutine task creator
    
    Raises:
        RuntimeError: If a weak reference listener was garbage collected
    """
    cdef object listener_ref
    cdef object listener
    cdef object result

    # Create a copy to allow modification during iteration
    for listener_ref in list(listeners):
        if isinstance(listener_ref, weakref.ref):
            listener = listener_ref()
            if listener is None:
                # Match Python behavior: raise RuntimeError
                raise RuntimeError(
                    'Listener has been garbage collected. '
                    'Consider using `keep_ref=True` if it suits your use case.'
                )
        else:
            listener = listener_ref

        result = listener(state)

        # Handle async listeners
        if asyncio.iscoroutine(result) and task_creator is not None:
            task_creator(result)


cpdef list apply_action_middlewares(list middlewares, object action):
    """
    Apply action middlewares in sequence.

    Returns the transformed action, or None if any middleware filtered it.
    """
    cdef object middleware
    cdef object result

    for middleware in middlewares:
        result = middleware(action)
        if result is None:
            return [None, False]  # Action was filtered
        action = result

    return [action, True]


cpdef list apply_event_middlewares(list middlewares, object event):
    """
    Apply event middlewares in sequence.

    Returns the transformed event, or None if any middleware filtered it.
    """
    cdef object middleware
    cdef object result

    for middleware in middlewares:
        result = middleware(event)
        if result is None:
            return [None, False]  # Event was filtered
        event = result

    return [event, True]


cpdef bint run_dispatch_loop(
    object store,
    object reducer,
    list action_middlewares,
    list event_middlewares,
    object is_complete_reducer_result,
    object is_state_reducer_result,
    object BaseAction,
    object BaseEvent,
    object FinishAction,
    object FinishEvent,
):
    """
    Optimized main dispatch loop.

    This is the hot path for state updates.

    Returns True if work was done, False otherwise.
    """
    cdef bint did_work = False
    cdef object action
    cdef object event
    cdef object result
    cdef object state = store._state
    cdef list actions_list = store._actions
    cdef list events_list = store._events

    # Process actions
    while len(actions_list) > 0:
        did_work = True
        action = actions_list.pop(0)

        if action is not None:
            result = reducer(state, action)

            if is_complete_reducer_result(result):
                state = result.state
                store._state = state
                call_listeners_fast(
                    store._listeners,
                    state,
                    store.store_options.task_creator
                )
                # Dispatch additional actions/events from result
                if result.actions:
                    for a in result.actions:
                        _dispatch_item(
                            store,
                            a,
                            action_middlewares,
                            event_middlewares,
                            BaseAction,
                            BaseEvent,
                        )
                if result.events:
                    for e in result.events:
                        _dispatch_item(
                            store,
                            e,
                            action_middlewares,
                            event_middlewares,
                            BaseAction,
                            BaseEvent,
                        )

            elif is_state_reducer_result(result):
                state = result
                store._state = state
                call_listeners_fast(
                    store._listeners,
                    state,
                    store.store_options.task_creator
                )

            if isinstance(action, FinishAction):
                events_list.append(FinishEvent())

    return did_work


cdef void _dispatch_item(
    object store,
    object item,
    list action_middlewares,
    list event_middlewares,
    object BaseAction,
    object BaseEvent,
):
    """Dispatch a single item (action or event) through middlewares."""
    cdef list middleware_result
    cdef object transformed

    if isinstance(item, BaseAction):
        if action_middlewares:
            middleware_result = apply_action_middlewares(action_middlewares, item)
            if middleware_result[1]:
                store._actions.append(middleware_result[0])
        else:
            store._actions.append(item)

    if isinstance(item, BaseEvent):
        if event_middlewares:
            middleware_result = apply_event_middlewares(event_middlewares, item)
            if middleware_result[1]:
                store._events.append(middleware_result[0])
        else:
            store._events.append(item)
