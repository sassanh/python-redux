"""Provide store for tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

    from redux.main import Store


@pytest.fixture
def store() -> Store:  # pragma: no cover
    """Provide current store (this is a placeholder returning None)."""
    msg = 'This fixture should be overridden.'
    raise NotImplementedError(msg)


@pytest.fixture
def needs_finish(store: Store) -> Generator:
    """Dispatch a finish action after the test."""
    yield None

    from redux import FinishAction

    store.dispatch(FinishAction())
