"""Pytest plugin for python-redux."""

import pytest


@pytest.hookimpl
def pytest_addoption(parser: pytest.Parser) -> None:
    """Add options to the pytest command line."""
    group = parser.getgroup('redux', 'python redux options')
    group.addoption('--override-store-snapshots', action='store_true')
