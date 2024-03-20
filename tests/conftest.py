"""Pytest configuration file for the tests."""

from __future__ import annotations

import datetime
import random
import time
import uuid

import pytest

pytest.register_assert_rewrite('redux.test')

from redux.test import pytest_addoption, store_snapshot  # noqa: E402

__all__ = ('store_snapshot', 'pytest_addoption')


@pytest.fixture(autouse=True)
def _(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock external resources."""
    random.seed(0)

    class DateTime(datetime.datetime):
        @classmethod
        def now(cls: type[DateTime], tz: datetime.tzinfo | None = None) -> DateTime:
            _ = tz
            return DateTime(2023, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)

    monkeypatch.setattr(datetime, 'datetime', DateTime)
    monkeypatch.setattr(
        time,
        'time',
        lambda: datetime.datetime.now(tz=datetime.timezone.utc).timestamp(),
    )
    monkeypatch.setattr(uuid, 'uuid4', lambda: uuid.UUID(int=random.getrandbits(128)))
