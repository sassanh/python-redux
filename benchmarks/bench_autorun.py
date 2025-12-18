
import pytest
from redux.main import Store
from redux.basic_types import BaseAction, StoreOptions
from dataclasses import replace, field
from immutable import Immutable

class State(Immutable):
    value: int
    nested: dict = field(default_factory=dict)

class IncrementAction(BaseAction):
    pass

def reducer(state, action):
    if state is None:
        return State(value=0)
    if isinstance(action, IncrementAction):
        return replace(state, value=state.value + 1)
    return state

@pytest.fixture
def store():
    return Store(reducer, options=StoreOptions(auto_init=True))

def test_autorun_creation(benchmark, store):
    """Benchmark creating autoruns."""
    
    def run():
        @store.autorun(lambda s: s.value)
        def _(val):
            pass

    benchmark(run)

def test_autorun_reactivity(benchmark, store):
    """Benchmark autorun reaction overhead."""
    
    @store.autorun(lambda s: s.value)
    def _(val):
        pass
    
    def run():
        store.dispatch(IncrementAction())

    benchmark(run)

def test_autorun_complex_selector(benchmark, store):
    """Benchmark autorun with complex selector."""
    
    @store.autorun(lambda s: s.value * 2 + (s.nested.get('a', 0) or 0))
    def _(val):
        pass

    def run():
        store.dispatch(IncrementAction())

    benchmark(run)

def test_autorun_many_subscribers(benchmark, store):
    """Benchmark notification of many autoruns."""
    
    for _ in range(100):
        @store.autorun(lambda s: s.value)
        def _(val):
            pass

    def run():
        store.dispatch(IncrementAction())

    benchmark(run)
