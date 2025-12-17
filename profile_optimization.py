import cProfile
import pstats
from redux.basic_types import BaseAction, StoreOptions
from redux.main import Store

class IncrementAction(BaseAction):
    pass

def reducer(state, action):
    if state is None:
        return 0
    return state + 1

# Setup Store
store = Store(reducer)

# Add subscribers to mimic heavy load
listeners = [lambda s: None for _ in range(1000)]
for l in listeners:
    store._subscribe(l)

def run_benchmark():
    for _ in range(100):
        store.dispatch(IncrementAction())

# Profile
print("Running profiling...")
cProfile.run('run_benchmark()', 'logs/profile_subscribers.prof')

# Print stats
stats = pstats.Stats('logs/profile_subscribers.prof')
stats.strip_dirs().sort_stats('cumtime').print_stats(30)
