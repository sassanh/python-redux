"""Utility fixtures for testing redux store."""

import pytest

pytest.register_assert_rewrite(
    'redux_pytest.fixtures.event_loop',
    'redux_pytest.fixtures.monitor',
    'redux_pytest.fixtures.snapshot',
    'redux_pytest.fixtures.store',
    'redux_pytest.fixtures.wait_for',
)

from .event_loop import LoopThread, event_loop  # noqa: E402
from .monitor import StoreMonitor, store_monitor  # noqa: E402
from .snapshot import StoreSnapshot, snapshot_prefix, store_snapshot  # noqa: E402
from .store import needs_finish, store  # noqa: E402
from .wait_for import Waiter, WaitFor, wait_for  # noqa: E402

__all__ = (
    'LoopThread',
    'StoreMonitor',
    'StoreSnapshot',
    'WaitFor',
    'Waiter',
    'event_loop',
    'needs_finish',
    'snapshot_prefix',
    'store',
    'store_monitor',
    'store_snapshot',
    'wait_for',
)
