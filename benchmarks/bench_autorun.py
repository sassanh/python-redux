
from dataclasses import field, replace

import pytest
from immutable import Immutable

from redux.basic_types import BaseAction, StoreOptions
from redux.main import Store


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

def test_autorun_creation(benchmark, store) -> None:
    """Benchmark creating autoruns."""

    def run() -> None:
        @store.autorun(lambda s: s.value)
        def _(val) -> None:
            pass

    benchmark(run)

def test_autorun_reactivity(benchmark, store) -> None:
    """Benchmark autorun reaction overhead."""

    @store.autorun(lambda s: s.value)
    def _(val) -> None:
        pass

    def run() -> None:
        store.dispatch(IncrementAction())

    benchmark(run)

def test_autorun_complex_selector(benchmark, store) -> None:
    """Benchmark autorun with complex selector."""

    @store.autorun(lambda s: s.value * 2 + (s.nested.get('a', 0) or 0))
    def _(val) -> None:
        pass

    def run() -> None:
        store.dispatch(IncrementAction())

    benchmark(run)

def test_autorun_many_subscribers(benchmark, store) -> None:
    """Benchmark notification of many autoruns."""
    for _ in range(100):
        @store.autorun(lambda s: s.value)
        def _(val) -> None:
            pass

    def run() -> None:
        store.dispatch(IncrementAction())

    benchmark(run)
