# ruff: noqa: S101
"""Let the test check snapshots of the window during execution."""
from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from logging import Logger
    from pathlib import Path

    from _pytest.fixtures import SubRequest

    from redux.main import Store


override_store_snapshots = os.environ.get('REDUX_TEST_OVERRIDE_SNAPSHOTS', '0') == '1'


class StoreSnapshotContext:
    """Context object for tests taking snapshots of the store."""

    def __init__(
        self: StoreSnapshotContext,
        test_id: str,
        path: Path,
        logger: Logger,
    ) -> None:
        """Create a new store snapshot context."""
        self.test_counter = 0
        self.id = test_id
        self.results_dir = path.parent / 'results'
        self.logger = logger
        self.results_dir.mkdir(exist_ok=True)

    def set_store(self: StoreSnapshotContext, store: Store) -> None:
        """Set the store to take snapshots of."""
        self.store = store

    @property
    def snapshot(self: StoreSnapshotContext) -> str:
        """Return the snapshot of the current state of the store."""
        return (
            json.dumps(self.store.snapshot, indent=2)
            if self.store._state  # noqa: SLF001
            else ''
        )

    def take(self: StoreSnapshotContext, title: str | None = None) -> None:
        """Take a snapshot of the current window."""
        if title:
            filename = f"""store:{"_".join(self.id.split(":")[-1:])}:{title}-{
            self.test_counter:03d}"""
        else:
            filename = (
                f'store:{"_".join(self.id.split(":")[-1:])}-{self.test_counter:03d}'
            )

        path = self.results_dir / filename
        json_path = path.with_suffix('.json')

        new_snapshot = self.snapshot
        if json_path.exists() and not override_store_snapshots:
            old_snapshot = json_path.read_text()
            if old_snapshot != new_snapshot:
                path.with_suffix('.mismatch.json').write_text(new_snapshot)
            assert old_snapshot == new_snapshot
        json_path.write_text(new_snapshot)

        self.test_counter += 1


@pytest.fixture()
def snapshot_store(request: SubRequest, logger: Logger) -> StoreSnapshotContext:
    """Take a snapshot of the current state of the store."""
    return StoreSnapshotContext(
        request.node.nodeid,
        request.node.path,
        logger,
    )
