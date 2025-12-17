"""Redux store for managing state and side effects."""

from __future__ import annotations

import os

# Re-export basic types for compatibility with legacy imports
from redux.basic_types import *
_FORCE_PYTHON = os.environ.get('REDUX_FORCE_PYTHON', '0') == '1'

if not _FORCE_PYTHON:
    try:
        from redux._store_core import Store
        _USE_CYTHON = True
    except ImportError:
        from redux._store_py import Store
        _USE_CYTHON = False
else:
    from redux._store_py import Store
    _USE_CYTHON = False

__all__ = ('Store',)
