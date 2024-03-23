"""Utility fixtures for testing redux store."""

import pytest

pytest.register_assert_rewrite('redux_pytest.fixtures.event_loop')
pytest.register_assert_rewrite('redux_pytest.fixtures.monitor')
pytest.register_assert_rewrite('redux_pytest.fixtures.snapshot')
pytest.register_assert_rewrite('redux_pytest.fixtures.store')
pytest.register_assert_rewrite('redux_pytest.fixtures.wait_for')

from .event_loop import LoopThread, event_loop  # noqa: E402
from .monitor import StoreMonitor, store_monitor  # noqa: E402
from .snapshot import StoreSnapshot, store_snapshot  # noqa: E402
from .store import needs_finish, store  # noqa: E402
from .wait_for import Waiter, WaitFor, wait_for  # noqa: E402

__all__ = [
    'LoopThread',
    'StoreMonitor',
    'StoreSnapshot',
    'Waiter',
    'WaitFor',
    'event_loop',
    'needs_finish',
    'store',
    'store_monitor',
    'store_snapshot',
    'wait_for',
]
