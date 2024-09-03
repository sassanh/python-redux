"""Monitor behavior of store for testing."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from redux.basic_types import BaseAction, BaseEvent
    from redux.main import Store


class StoreMonitor:
    """Monitor the behavior of a store for testing."""

    def __init__(self: StoreMonitor, mocker: MockerFixture) -> None:
        """Initialize the store monitor."""
        self.store = None
        self._mocker = mocker
        self.dispatched_actions = mocker.spy(self, '_action_middleware')
        self.dispatched_events = mocker.spy(self, '_event_middleware')

    def _action_middleware(self: StoreMonitor, action: BaseAction) -> BaseAction:
        return action

    def _event_middleware(self: StoreMonitor, event: BaseEvent) -> BaseEvent:
        return event

    def monitor(self: StoreMonitor, store: Store) -> None:
        """Set the store to monitor."""
        if self.store:
            self.store.unregister_action_middleware(self._action_middleware)
            self.store.unregister_event_middleware(self._event_middleware)
        self.store = store
        self.store.register_action_middleware(self._action_middleware)
        self.store.register_event_middleware(self._event_middleware)


@pytest.fixture
def store_monitor(store: Store, mocker: MockerFixture) -> StoreMonitor:
    """Fixture to check if an action was dispatched."""
    monitor = StoreMonitor(mocker)

    if store:
        monitor.monitor(store)

    return monitor
