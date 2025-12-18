# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: nonecheck=False
# cython: cdivision=True

import uuid
import copy
import functools
import operator
from dataclasses import fields
from typing import TypeVar

from .basic_types import (
    BaseAction,
    BaseEvent,
    BaseCombineReducerState,
    CombineReducerAction,
    CombineReducerInitAction,
    CombineReducerRegisterAction,
    CombineReducerUnregisterAction,
    CompleteReducerResult,
    InitAction,
    is_complete_reducer_result,
    NOT_SET
)
from immutable import make_immutable

cdef class CombinedReducer:
    cdef object state_type
    cdef object state_class
    cdef dict reducers
    cdef str id_

    def __init__(self, state_type, reducers, id_):
        self.state_type = state_type
        self.reducers = reducers
        self.id_ = id_
        self._update_state_class()

    cdef object state_accessor

    cdef _update_state_class(self):
        self.state_class = make_immutable(
            self.state_type.__name__,
            (('combine_reducers_id', str), *self.reducers.keys()),
        )
        if self.reducers:
            self.state_accessor = operator.attrgetter(*self.reducers.keys())
        else:
            self.state_accessor = None

    def __call__(self, state, action):
        cdef list result_actions = []
        cdef list result_events = []
        cdef object key
        cdef object reducer
        cdef object reducer_result
        cdef object sub_state
        cdef object sub_states
        
        # Handle Registration/Unregistration (Slow Path)
        if (
            state is not None
            and isinstance(action, CombineReducerAction)
            and action.combine_reducers_id == self.id_
        ):
            if isinstance(action, CombineReducerRegisterAction):
                key = action.key
                reducer = action.reducer
                self.reducers[key] = reducer
                self._update_state_class()
                
                reducer_result = reducer(
                    None,
                    CombineReducerInitAction(
                        combine_reducers_id=self.id_,
                        key=key,
                        payload=action.payload,
                    ),
                )
                
                # Reconstruct state with new key
                new_state_kwargs = {'combine_reducers_id': state.combine_reducers_id}
                for k in self.reducers:
                    if k == key:
                        new_state_kwargs[k] = (
                            reducer_result.state
                            if is_complete_reducer_result(reducer_result)
                            else reducer_result
                        )
                    else:
                        new_state_kwargs[k] = getattr(state, k)
                
                state = self.state_class(**new_state_kwargs)
                
                if is_complete_reducer_result(reducer_result):
                    if reducer_result.actions:
                        result_actions.extend(reducer_result.actions)
                    if reducer_result.events:
                        result_events.extend(reducer_result.events)

            elif isinstance(action, CombineReducerUnregisterAction):
                key = action.key
                del self.reducers[key]
                
                # Update state class structure manually (mimicking Python implementation)
                fields_copy = {field.name: field for field in fields(self.state_class)}
                annotations_copy = copy.deepcopy(self.state_class.__annotations__)
                del fields_copy[key]
                del annotations_copy[key]
                self.state_class = make_immutable(self.state_type.__name__, annotations_copy)
                self.state_class.__dataclass_fields__ = fields_copy
                
                # Update state accessor
                if self.reducers:
                    self.state_accessor = operator.attrgetter(*self.reducers.keys())
                else:
                    self.state_accessor = None

                new_state_kwargs = {'combine_reducers_id': state.combine_reducers_id}
                for k in self.reducers:
                    new_state_kwargs[k] = getattr(state, k)
                state = self.state_class(**new_state_kwargs)

        # Dispatch Loop (Hot Path)
        cdef bint is_init = isinstance(action, InitAction)
        
        # Pre-allocate kwargs for result state
        cdef dict result_state_kwargs = {'combine_reducers_id': self.id_}
        
        # Optimize State Access
        if state is None:
            sub_states = None
        elif self.state_accessor:
            sub_states = self.state_accessor(state)
            if len(self.reducers) == 1:
                sub_states = (sub_states,)
        else:
             sub_states = ()

        cdef int idx = 0
        for key, reducer in self.reducers.items():
            if sub_states is not None:
                sub_state = sub_states[idx]
            else:
                sub_state = None
            idx += 1
            
            sub_action = action
            if is_init:
                sub_action = CombineReducerInitAction(key=key, combine_reducers_id=self.id_)
            
            res = reducer(sub_state, sub_action)
            
            if is_complete_reducer_result(res):
                result_state_kwargs[key] = res.state
                if res.actions:
                    result_actions.extend(res.actions)
                if res.events:
                    result_events.extend(res.events)
            else:
                result_state_kwargs[key] = res

        result_state = self.state_class(**result_state_kwargs)

        return CompleteReducerResult(
            state=result_state,
            actions=result_actions,
            events=result_events,
        )

def combine_reducers(
    state_type,
    action_type=BaseAction,
    event_type=BaseEvent,
    **reducers,
):
    id_ = uuid.uuid4().hex
    # Copy reducers dict
    reducers_copy = reducers.copy()
    
    combined = CombinedReducer(state_type, reducers_copy, id_)
    return combined, id_
