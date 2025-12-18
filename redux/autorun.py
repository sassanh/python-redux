"""Redux autorun module."""
from __future__ import annotations

from typing import TYPE_CHECKING

from .main import _USE_CYTHON

if TYPE_CHECKING:
    from ._autorun_py import Autorun
elif _USE_CYTHON:
    try:
        from ._store_core import Autorun
    except ImportError:
        from ._autorun_py import Autorun
else:
    from ._autorun_py import Autorun

__all__ = ('Autorun',)
