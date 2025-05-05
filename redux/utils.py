"""Utility functions for the project."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


def is_method(func: Callable) -> bool:
    """Check if the function is a method."""
    signature = inspect.signature(func)
    return (
        len(signature.parameters) > 0
        and next(iter(signature.parameters.values())).name == 'self'
    )


def signature_without_selector(func: Callable) -> inspect.Signature:
    """Drop the parameter associated consumed by the with_store/autorun/view wrapper."""
    signature = inspect.signature(func)
    parameters = list(signature.parameters.values())
    self_parameter: list[inspect.Parameter] = []
    if is_method(func):
        self_parameter = [parameters[0]]
        parameters = parameters[1:]
    if parameters and parameters[0].kind in [
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    ]:
        parameters = parameters[1:]
    return signature.replace(parameters=self_parameter + parameters)


def call_func(
    func: Callable,
    injecting_args: list,
    *args: tuple,
    **kwargs: dict,
) -> Any:  # noqa: ANN401
    """Call function `func` respecting whether it is a method or a function."""
    if is_method(func):
        self_ = args[0]
        args_ = args[1:]
        return func(self_, *injecting_args, *args_, **kwargs)

    return func(*injecting_args, *args, **kwargs)
