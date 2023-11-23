# ruff: noqa: A003, D100, D101, D102, D103, D104, D105, D107
from __future__ import annotations

import copy
import uuid
from dataclasses import asdict, make_dataclass
from typing import TYPE_CHECKING, Any, Literal, TypeGuard, TypeVar, cast

from .basic_types import (
    Action,
    BaseAction,
    CompleteReducerResult,
    Immutable,
    InitAction,
    State,
    is_reducer_result,
)

if TYPE_CHECKING:
    from redux import ReducerType


class BaseCombineReducerState(Immutable):
    _id: str


class BaseCombineReducerAction(BaseAction):
    _id: str


class CombineReducerRegisterActionPayload(Immutable):
    key: str
    reducer: ReducerType


class CombineReducerRegisterAction(BaseCombineReducerAction):
    payload: CombineReducerRegisterActionPayload
    type: Literal['REGISTER'] = 'REGISTER'


class CombineReducerUnregisterActionPayload(Immutable):
    key: str


class CombineReducerUnregisterAction(BaseCombineReducerAction):
    payload: CombineReducerUnregisterActionPayload
    type: Literal['UNREGISTER'] = 'UNREGISTER'


CombineReducerAction = CombineReducerRegisterAction | CombineReducerUnregisterAction
CombineReducerState = TypeVar(
    'CombineReducerState',
    bound=BaseCombineReducerState,
)
AnyAction = TypeVar('AnyAction', bound=BaseAction)


def is_combine_reducer_action(action: BaseAction) -> TypeGuard[CombineReducerAction]:
    return isinstance(action, BaseCombineReducerAction)


def combine_reducers(
    action_type: type[Action],  # noqa: ARG001
    state_type: type[CombineReducerState],
    **reducers: ReducerType[State, AnyAction],
) -> tuple[ReducerType[CombineReducerState, Action], str]:
    _id = uuid.uuid4().hex

    state_class = cast(
        type[state_type],
        make_dataclass(
            'combined_reducer',
            ('_id', *reducers.keys()),
            frozen=True,
            kw_only=True,
        ),
    )

    def combined_reducer(
        state: CombineReducerState | None,
        action: Action,
    ) -> CompleteReducerResult[CombineReducerState, Action]:
        nonlocal state_class
        if state is not None and is_combine_reducer_action(action):
            if action.type == 'REGISTER' and action._id == _id:  # noqa: SLF001
                key = action.payload.key
                reducer = action.payload.reducer
                reducers[key] = reducer
                state_class = make_dataclass(
                    'combined_reducer',
                    ('_id', *reducers.keys()),
                    frozen=True,
                )
                state = state_class(
                    _id=state._id,  # noqa: SLF001
                    **(
                        {
                            key_: reducer(
                                None,
                                InitAction(type='INIT'),
                            )
                            if key == key_
                            else getattr(state, key_)
                            for key_ in reducers
                        }
                    ),
                )
            elif action.type == 'UNREGISTER' and action._id == _id:  # noqa: SLF001
                key = action.payload.key

                del reducers[key]
                fields_copy = copy.copy(cast(Any, state_class).__dataclass_fields__)
                annotations_copy = copy.deepcopy(state_class.__annotations__)
                del fields_copy[key]
                del annotations_copy[key]
                state_class = make_dataclass('combined_reducer', annotations_copy)
                cast(Any, state_class).__dataclass_fields__ = fields_copy

                state = state_class(
                    **{
                        key_: getattr(state, key_)
                        for key_ in asdict(state)
                        if key_ != key
                    },
                )

        reducers_results = {
            key: reducer(
                None if state is None else getattr(state, key),
                cast(AnyAction, action),
            )
            for key, reducer in reducers.items()
        }
        result_state = state_class(
            _id=_id,
            **{
                key: result.state if is_reducer_result(result) else result
                for key, result in reducers_results.items()
            },
        )
        result_actions = cast(
            list[Action],
            sum(
                [
                    result.actions or [] if is_reducer_result(result) else []
                    for result in reducers_results.values()
                ],
                [],
            ),
        )
        result_side_effects = sum(
            [
                result.side_effects or [] if is_reducer_result(result) else []
                for result in reducers_results.values()
            ],
            [],
        )

        return CompleteReducerResult(
            state=result_state,
            actions=result_actions,
            side_effects=result_side_effects,
        )

    return (combined_reducer, _id)