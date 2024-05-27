# ruff: noqa: S101
"""Let the test check snapshots of the window during execution."""

from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Generic, cast

import pytest

from redux.basic_types import FinishEvent, State

if TYPE_CHECKING:
    from _pytest.fixtures import SubRequest

    from redux.main import Store


class StoreSnapshot(Generic[State]):
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
        self._is_failed = False
        self._is_closed = False
        self.override = override
        self.test_counter: dict[str | None, int] = defaultdict(int)
        file = path.with_suffix('').name
        self.results_dir = Path(
            path.parent / 'results' / file / test_id.split('::')[-1][5:],
        )
        if self.results_dir.exists():
            for file in self.results_dir.glob(
                'store-*.jsonc' if override else 'store-*.mismatch.jsonc',
            ):
                file.unlink()  # pragma: no cover
        self.results_dir.mkdir(parents=True, exist_ok=True)

        self.store = store
        store.subscribe_event(FinishEvent, self.close)

    def json_snapshot(
        self: StoreSnapshot[State],
        *,
        selector: Callable[[State], Any] = lambda state: state,
    ) -> str:
        """Return the snapshot of the current state of the store."""
        return (
            json.dumps(
                self.store.serialize_value(selector(self.store._state)),  # noqa: SLF001
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
            if self.store._state  # noqa: SLF001
            else ''
        )

    def get_filename(self: StoreSnapshot[State], title: str | None) -> str:
        """Get the filename for the snapshot."""
        if title:
            return f"""store-{title}-{self.test_counter[title]:03d}"""
        return f"""store-{self.test_counter[title]:03d}"""

    def take(
        self: StoreSnapshot[State],
        *,
        title: str | None = None,
        selector: Callable[[State], Any] = lambda state: state,
    ) -> None:
        """Take a snapshot of the current window."""
        if self._is_closed:
            msg = (
                'Snapshot context is closed, make sure you are not calling `take` '
                'after `FinishEvent` is dispatched.'
            )
            raise RuntimeError(msg)

        from pathlib import Path

        filename = self.get_filename(title)
        path = Path(self.results_dir / filename)
        json_path = path.with_suffix('.jsonc')
        mismatch_path = path.with_suffix('.mismatch.jsonc')

        new_snapshot = self.json_snapshot(selector=selector)
        if self.override:
            json_path.write_text(f'// {filename}\n{new_snapshot}\n')  # pragma: no cover
        else:
            try:
                old_snapshot = json_path.read_text().split('\n', 1)[1][:-1]
            except Exception:  # noqa: BLE001
                old_snapshot = None
            if old_snapshot != new_snapshot:
                self._is_failed = True
                mismatch_path.write_text(  # pragma: no cover
                    f'// MISMATCH: {filename}\n{new_snapshot}\n',
                )
            assert new_snapshot == old_snapshot, f'Store snapshot mismatch - {filename}'

        self.test_counter[title] += 1

    def monitor(self: StoreSnapshot[State], selector: Callable[[State], Any]) -> None:
        """Monitor the state of the store and take snapshots."""

        @self.store.autorun(selector=selector)
        def _(state: State) -> None:
            self.take(selector=lambda _: state)

    def close(self: StoreSnapshot[State]) -> None:
        """Close the snapshot context."""
        self._is_closed = True
        if self._is_failed:
            return
        for title in self.test_counter:
            filename = self.get_filename(title)
            json_path = (self.results_dir / filename).with_suffix('.jsonc')

            assert not json_path.exists(), f'Snapshot {filename} not taken'


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
