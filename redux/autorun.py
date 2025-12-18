"""Redux autorun module."""
from __future__ import annotations

from .main import _USE_CYTHON

if _USE_CYTHON:
    try:
        from ._store_core import Autorun
    except ImportError:
        from ._autorun_py import Autorun
else:
    from ._autorun_py import Autorun
