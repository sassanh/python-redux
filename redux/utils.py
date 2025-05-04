"""Utility functions for the project."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


def drop_with_store_parameter(func: Callable) -> inspect.Signature:
    """Drop the parameter associated consumed by the with_store/autorun/view wrapper."""
    signature = inspect.signature(func)
    parameters = list(signature.parameters.values())
    self_parameter: list[inspect.Parameter] = []
    is_method = parameters and parameters[0].name == 'self'
    if is_method:
        self_parameter = [parameters[0]]
        parameters = parameters[1:]
    if parameters and parameters[0].kind in [
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    ]:
        parameters = parameters[1:]
    return signature.replace(parameters=self_parameter + parameters)
