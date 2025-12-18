"""Redux combine_reducers module."""
from __future__ import annotations

from typing import TYPE_CHECKING

from .main import _USE_CYTHON

if TYPE_CHECKING:
    from ._combine_reducers_py import combine_reducers
elif _USE_CYTHON:
    try:
        from ._combine_reducers import combine_reducers
    except ImportError:
        from ._combine_reducers_py import combine_reducers
else:
    from ._combine_reducers_py import combine_reducers

__all__ = ('combine_reducers',)
