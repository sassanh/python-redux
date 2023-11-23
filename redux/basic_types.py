# ruff: noqa: A003, D100, D101, D102, D103, D104, D105, D107
from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Generic,
    Literal,
    Mapping,
    TypeGuard,
    TypeVar,
    dataclass_transform,
)

_T = TypeVar('_T')


@dataclass_transform(kw_only_default=True, frozen_default=True)
def immutable(cls: type[_T]) -> type[_T]:
    return dataclass(frozen=True, kw_only=True)(cls)


@dataclass_transform(kw_only_default=True, frozen_default=True)
class Immutable:
    def __init_subclass__(
        cls: type[Immutable],
        **kwargs: Mapping[str, Any],
    ) -> None:
        super().__init_subclass__(**kwargs)
        immutable(cls)


class BaseAction(Immutable):
    type: str


# Type variables
State = TypeVar('State', bound=Immutable)
State_co = TypeVar('State_co', covariant=True)
Action = TypeVar('Action', bound=BaseAction)
SelectorOutput = TypeVar('SelectorOutput')
SelectorOutput_co = TypeVar('SelectorOutput_co', covariant=True)
SelectorOutput_contra = TypeVar('SelectorOutput_contra', contravariant=True)
ComparatorOutput = TypeVar('ComparatorOutput')
Selector = Callable[[State], SelectorOutput]
Comparator = Callable[[State], ComparatorOutput]
SideEffect = Callable[[], None]


class CompleteReducerResult(Immutable, Generic[State, Action]):
    state: State
    actions: list[Action] | None = None
    side_effects: list[SideEffect] | None = None


ReducerResult = CompleteReducerResult[State, Action] | State


ReducerType = Callable[[State | None, Action], ReducerResult[State, Action]]
AutorunReturnType = TypeVar('AutorunReturnType')
AutorunReturnType_co = TypeVar('AutorunReturnType_co', covariant=True)


class InitializationActionError(Exception):
    def __init__(self: InitializationActionError) -> None:
        super().__init__(
            'The only accepted action type when state is None is "INIT"',
        )


class InitAction(BaseAction):
    type: Literal['INIT'] = 'INIT'


class FinishAction(BaseAction):
    type: Literal['FINISH'] = 'FINISH'


def is_reducer_result(
    result: ReducerResult[State, Action],
) -> TypeGuard[CompleteReducerResult[State, Action]]:
    return isinstance(result, CompleteReducerResult)


def is_state(result: ReducerResult[State, Action]) -> TypeGuard[State]:
    return not isinstance(result, CompleteReducerResult)
