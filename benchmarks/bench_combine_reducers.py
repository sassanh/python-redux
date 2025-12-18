
from __future__ import annotations
import uuid
from typing import Any
import pytest
from redux import (
    BaseAction,
    BaseEvent,
    CompleteReducerResult,
    InitAction,
    combine_reducers,
)
from redux.basic_types import Immutable

class State(Immutable):
    value: int

class IncrementAction(BaseAction):
    pass

def counter_reducer(state: State | None, action: Any) -> State:
    if state is None:
        return State(value=0)
    if isinstance(action, IncrementAction):
        return State(value=state.value + 1)
    return state

def create_reducers(count: int):
    return {f'r{i}': counter_reducer for i in range(count)}

@pytest.mark.benchmark(group='combine_reducers_creation')
def test_creation(benchmark):
    reducers = create_reducers(10)
    
    def run():
        combine_reducers(State, **reducers)
        
    benchmark(run)

@pytest.mark.benchmark(group='combine_reducers_dispatch')
def test_dispatch_10_reducers(benchmark):
    reducers = create_reducers(10)
    reducer, _ = combine_reducers(State, **reducers)
    state = reducer(None, InitAction()).state
    action = IncrementAction()
    
    def run():
        reducer(state, action)
        
    benchmark(run)

@pytest.mark.benchmark(group='combine_reducers_dispatch')
def test_dispatch_50_reducers(benchmark):
    reducers = create_reducers(50)
    reducer, _ = combine_reducers(State, **reducers)
    state = reducer(None, InitAction()).state
    action = IncrementAction()
    
    def run():
        reducer(state, action)
        
    benchmark(run)

@pytest.mark.benchmark(group='combine_reducers_dispatch')
def test_dispatch_100_reducers(benchmark):
    reducers = create_reducers(100)
    reducer, _ = combine_reducers(State, **reducers)
    state = reducer(None, InitAction()).state
    action = IncrementAction()
    
    def run():
        reducer(state, action)
        
    benchmark(run)
