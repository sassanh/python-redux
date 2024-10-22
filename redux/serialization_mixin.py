"""Mixin for serialization."""

from __future__ import annotations

import dataclasses
from types import NoneType
from typing import TYPE_CHECKING, Any

from immutable import Immutable, is_immutable

if TYPE_CHECKING:
    from redux.basic_types import SnapshotAtom


class SerializationMixin:
    """Mixin for serialization."""

    @classmethod
    def serialize_value(
        cls: type[SerializationMixin],
        obj: object | type,
    ) -> SnapshotAtom:
        """Serialize a value to a snapshot atom."""
        if isinstance(obj, int | float | str | bool | NoneType):
            return obj
        if callable(obj):
            return cls.serialize_value(obj())
        if isinstance(obj, list | tuple):
            return [cls.serialize_value(i) for i in obj]
        if is_immutable(obj):
            return cls._serialize_dataclass_to_dict(obj)
        msg = f'Unable to serialize object with type `{type(obj)}`'
        raise TypeError(msg)

    @classmethod
    def _serialize_dataclass_to_dict(
        cls: type[SerializationMixin],
        obj: Immutable,
    ) -> dict[str, Any]:
        result: dict[str, object] = {'_type': obj.__class__.__name__}
        for field in dataclasses.fields(obj):
            value = cls.serialize_value(getattr(obj, field.name))
            result[field.name] = value
        return result
