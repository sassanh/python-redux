"""A wrapper for functions that require the current state of the store."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Concatenate, Generic

from redux.basic_types import Action, Args, Event, ReturnType, SelectorOutput, State

if TYPE_CHECKING:
    from collections.abc import Callable

    from redux.main import Store


class WithState(Generic[State, Action, Event, SelectorOutput, ReturnType, Args]):
    """A wrapper for functions that require the current state of the store."""

    def __init__(
        self: WithState,
        *,
        store: Store[State, Action, Event],
        selector: Callable[[State], SelectorOutput],
        func: Callable[
            Concatenate[SelectorOutput, Args],
            ReturnType,
        ],
    ) -> None:
        """Initialize the WithState instance."""
        if hasattr(func, '__name__'):
            self.__name__ = f'WithState:{func.__name__}'
        else:
            self.__name__ = f'WithState:{func}'
        if hasattr(func, '__qualname__'):
            self.__qualname__ = f'WithState:{func.__qualname__}'
        else:
            self.__qualname__ = f'WithState:{func}'
        signature = inspect.signature(func)
        parameters = list(signature.parameters.values())
        if parameters and parameters[0].kind in [
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ]:
            parameters = parameters[1:]
        self.__signature__ = signature.replace(parameters=parameters)
        self.__module__ = func.__module__
        if (annotations := getattr(func, '__annotations__', None)) is not None:
            self.__annotations__ = annotations
        if (defaults := getattr(func, '__defaults__', None)) is not None:
            self.__defaults__ = defaults
        if (kwdefaults := getattr(func, '__kwdefaults__', None)) is not None:
            self.__kwdefaults__ = kwdefaults

        self._store = store
        self._selector = selector
        self._func = func

    def __call__(
        self: WithState[
            State,
            Action,
            Event,
            SelectorOutput,
            ReturnType,
            Args,
        ],
        *args: Args.args,
        **kwargs: Args.kwargs,
    ) -> ReturnType:
        """Call the wrapped function with the current state of the store."""
        if self._store._state is None:  # noqa: SLF001
            msg = 'Store has not been initialized yet.'
            raise RuntimeError(msg)
        return self._func(self._selector(self._store._state), *args, **kwargs)  # noqa: SLF001

    def __repr__(
        self: WithState[
            State,
            Action,
            Event,
            SelectorOutput,
            ReturnType,
            Args,
        ],
    ) -> str:
        """Return the string representation of the WithState instance."""
        return super().__repr__() + f'(func: {self._func})'
