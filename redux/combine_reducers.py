from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from .basic_types import (
    BaseCombineReducerState,
)

if TYPE_CHECKING:
    from ._combine_reducers_py import combine_reducers as combine_reducers_py


CombineReducerState = TypeVar(
    'CombineReducerState',
    bound=BaseCombineReducerState,
)


try:
    from ._combine_reducers import combine_reducers as combine_reducers_cy
    
    combine_reducers = combine_reducers_cy
except ImportError:
    from ._combine_reducers_py import combine_reducers
