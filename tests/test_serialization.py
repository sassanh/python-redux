# ruff: noqa: D100, D101, D102, D103, D104, D107
from __future__ import annotations

from typing import Callable

import pytest

from redux.main import Store


def test_int() -> None:
    assert Store.serialize_value(1) == 1


def test_float() -> None:
    assert Store.serialize_value(1.0) == 1.0


def test_str() -> None:
    assert Store.serialize_value('string') == 'string'


def test_bool() -> None:
    assert Store.serialize_value(obj=True) is True
    assert Store.serialize_value(obj=False) is False


def test_none() -> None:
    assert Store.serialize_value(None) is None


def test_callable() -> None:
    def func() -> str:
        return 'string'

    assert Store.serialize_value(func) == 'string'


def test_list() -> None:
    assert Store.serialize_value([1, 2, 3]) == [1, 2, 3]


class InvalidType: ...


def test_invalid() -> None:
    with pytest.raises(
        TypeError,
        match=f'^Unable to serialize object with type `{InvalidType}`$',
    ):
        Store.serialize_value(InvalidType())


def test_immutable() -> None:
    from immutable import Immutable

    class State(Immutable):
        integer: int
        floating_poing: float
        string: str
        boolean: bool
        none: None
        function: Callable
        list_: list[int]

    assert Store.serialize_value(
        State(
            integer=1,
            floating_poing=1.0,
            string='string',
            boolean=True,
            none=None,
            function=lambda: 'string',
            list_=[1, 2, 3],
        ),
    ) == {
        '_type': 'State',
        'integer': 1,
        'floating_poing': 1.0,
        'string': 'string',
        'boolean': True,
        'none': None,
        'function': 'string',
        'list_': [1, 2, 3],
    }
