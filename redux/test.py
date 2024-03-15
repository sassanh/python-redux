# ruff: noqa: S101
"""Let the test check snapshots of the window during execution."""
from __future__ import annotations

import dataclasses
import json
import os
from enum import IntEnum, StrEnum
from types import NoneType
from typing import TYPE_CHECKING, Any

import pytest
from immutable import Immutable, is_immutable

if TYPE_CHECKING:
    from logging import Logger
    from pathlib import Path

    from _pytest.fixtures import SubRequest

    from redux.main import Store


override_store_snapshots = os.environ.get('REDUX_TEST_OVERRIDE_SNAPSHOTS', '0') == '1'


Atom = int | float | str | bool | NoneType | dict[str, 'Atom'] | list['Atom']


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

    def _convert_value(self: StoreSnapshotContext, obj: object | type) -> Atom:
        import sys
        from pathlib import Path

        if is_immutable(obj):
            return self._convert_dataclass_to_dict(obj)
        if isinstance(obj, (list, tuple)):
            return [self._convert_value(i) for i in obj]
        if isinstance(obj, type):
            file_path = sys.modules[obj.__module__].__file__
            if file_path:
                return f"""{Path(file_path).relative_to(Path().absolute()).as_posix()}:{
                obj.__name__}"""
            return f'{obj.__module__}:{obj.__name__}'
        if callable(obj):
            return self._convert_value(obj())
        if isinstance(obj, StrEnum):
            return str(obj)
        if isinstance(obj, IntEnum):
            return int(obj)
        if isinstance(obj, (int, float, str, bool, NoneType)):
            return obj
        self.logger.warning(
            'Unable to serialize',
            extra={'type': type(obj), 'value': obj},
        )
        return None

    def _convert_dataclass_to_dict(
        self: StoreSnapshotContext,
        obj: Immutable,
    ) -> dict[str, Any]:
        result = {}
        for field in dataclasses.fields(obj):
            value = self._convert_value(getattr(obj, field.name))
            result[field.name] = value
        return result

    def set_store(self: StoreSnapshotContext, store: Store) -> None:
        """Set the store to take snapshots of."""
        self.store = store

    @property
    def snapshot(self: StoreSnapshotContext) -> str:
        """Return the snapshot of the current state of the store."""
        return (
            json.dumps(self._convert_value(self.store._state), indent=2)  # noqa: SLF001
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
