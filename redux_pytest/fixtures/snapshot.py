# ruff: noqa: S101
"""Let the test check snapshots of the window during execution."""

from __future__ import annotations

import json
import os
from collections import defaultdict
from typing import TYPE_CHECKING, Any, cast

import pytest

from redux.basic_types import FinishEvent

if TYPE_CHECKING:
    from pathlib import Path

    from _pytest.fixtures import SubRequest

    from redux.main import Store


class StoreSnapshot:
    """Context object for tests taking snapshots of the store."""

    def __init__(
        self: StoreSnapshot,
        *,
        test_id: str,
        path: Path,
        override: bool,
        store: Store,
    ) -> None:
        """Create a new store snapshot context."""
        self._is_closed = False
        self.override = override
        self.test_counter: dict[str | None, int] = defaultdict(int)
        file = path.with_suffix('').name
        self.results_dir = path.parent / 'results' / file / test_id.split('::')[-1][5:]
        if self.results_dir.exists():
            for file in self.results_dir.glob(
                'store-*' if override else 'store-*.mismatch.json',
            ):
                file.unlink()  # pragma: no cover
        self.results_dir.mkdir(parents=True, exist_ok=True)

        self.store = store
        store.subscribe_event(FinishEvent, self.close)

    @property
    def json_snapshot(self: StoreSnapshot) -> str:
        """Return the snapshot of the current state of the store."""
        return (
            json.dumps(
                self.store.snapshot,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
            if self.store._state  # noqa: SLF001
            else ''
        )

    def get_filename(self: StoreSnapshot, title: str | None) -> str:
        """Get the filename for the snapshot."""
        if title:
            return f"""store-{title}-{self.test_counter[title]:03d}"""
        return f"""store-{self.test_counter[title]:03d}"""

    def take(self: StoreSnapshot, *, title: str | None = None) -> None:
        """Take a snapshot of the current window."""
        if self._is_closed:
            msg = (
                'Snapshot context is closed, make sure you are not calling `take` '
                'after `FinishEvent` is dispatched.'
            )
            raise RuntimeError(msg)

        filename = self.get_filename(title)
        path = self.results_dir / filename
        json_path = path.with_suffix('.jsonc')
        mismatch_path = path.with_suffix('.mismatch.jsonc')

        new_snapshot = self.json_snapshot
        if self.override:
            json_path.write_text(f'// {filename}\n{new_snapshot}\n')  # pragma: no cover
        else:
            old_snapshot = None
            if json_path.exists():
                old_snapshot = json_path.read_text().split('\n', 1)[1][:-1]
            if old_snapshot != new_snapshot:
                mismatch_path.write_text(  # pragma: no cover
                    f'// MISMATCH: {filename}\n{new_snapshot}\n',
                )
            if title:
                assert (
                    new_snapshot == old_snapshot
                ), f'Store snapshot mismatch for {title}'
            else:
                assert new_snapshot == old_snapshot, 'Store snapshot mismatch'

        self.test_counter[title] += 1

    def close(self: StoreSnapshot) -> None:
        """Close the snapshot context."""
        for title in self.test_counter:
            filename = self.get_filename(title)
            json_path = (self.results_dir / filename).with_suffix('.jsonc')

            assert not json_path.exists(), f'Snapshot {filename} not taken'
        self._is_closed = True


@pytest.fixture()
def store_snapshot(request: SubRequest, store: Store) -> StoreSnapshot:
    """Take a snapshot of the current state of the store."""
    override = (
        request.config.getoption(
            '--override-store-snapshots',
            default=cast(
                Any,
                os.environ.get('REDUX_TEST_OVERRIDE_SNAPSHOTS', '0') == '1',
            ),
        )
        is True
    )
    return StoreSnapshot(
        test_id=request.node.nodeid,
        path=request.node.path,
        override=override,
        store=store,
    )
