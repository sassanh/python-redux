# ruff: noqa: A003, D100, D101, D102, D103, D104, D105, D107
from __future__ import annotations

import copy
import functools
import operator
import uuid
from dataclasses import fields
from typing import TYPE_CHECKING, TypeVar

from immutable import make_immutable

from .basic_types import (
    Action,
    BaseAction,
    BaseCombineReducerState,
    BaseEvent,
    CombineReducerAction,
    CombineReducerInitAction,
    CombineReducerRegisterAction,
    CombineReducerUnregisterAction,
    CompleteReducerResult,
    Event,
    InitAction,
    is_complete_reducer_result,
)

if TYPE_CHECKING:
    from redux import ReducerType


CombineReducerState = TypeVar(
    'CombineReducerState',
    bound=BaseCombineReducerState,
)
AnyAction = TypeVar('AnyAction', bound=BaseAction)


def combine_reducers(
    state_type: type[CombineReducerState],
    action_type: type[Action] = BaseAction,
    event_type: type[Event] = BaseEvent,
    **reducers: ReducerType,
) -> tuple[ReducerType[CombineReducerState, Action, Event], str]:
    _ = action_type, event_type
    reducers = reducers.copy()
    _id = uuid.uuid4().hex

    state_class = make_immutable(state_type.__name__, (('_id', str), *reducers.keys()))

    def combined_reducer(
        state: CombineReducerState | None,
        action: Action,
    ) -> CompleteReducerResult[CombineReducerState, Action, Event]:
        result_actions = []
        result_events = []
        nonlocal state_class
        if (
            state is not None
            and isinstance(action, CombineReducerAction)
            and action._id == _id  # noqa: SLF001
        ):
            if isinstance(action, CombineReducerRegisterAction):
                key = action.key
                reducer = action.reducer
                reducers[key] = reducer
                state_class = make_immutable(
                    state_type.__name__,
                    (('_id', str), *reducers.keys()),
                )
                reducer_result = reducer(
                    None,
                    CombineReducerInitAction(_id=_id, key=key, payload=action.payload),
                )
                state = state_class(
                    _id=state._id,  # noqa: SLF001
                    **{
                        key_: (
                            reducer_result.state
                            if is_complete_reducer_result(reducer_result)
                            else reducer_result
                        )
                        if key == key_
                        else getattr(state, key_)
                        for key_ in reducers
                    },
                )
                result_actions += (
                    reducer_result.actions or []
                    if is_complete_reducer_result(reducer_result)
                    else []
                )
                result_events += (
                    reducer_result.events or []
                    if is_complete_reducer_result(reducer_result)
                    else []
                )
            elif isinstance(action, CombineReducerUnregisterAction):
                key = action.key

                del reducers[key]
                fields_copy = {field.name: field for field in fields(state_class)}
                annotations_copy = copy.deepcopy(state_class.__annotations__)
                del fields_copy[key]
                del annotations_copy[key]
                state_class = make_immutable(state_type.__name__, annotations_copy)
                state_class.__dataclass_fields__ = fields_copy

                state = state_class(
                    _id=state._id,  # noqa: SLF001
                    **{key_: getattr(state, key_) for key_ in reducers if key_ != key},
                )

        reducers_results = {
            key: reducer(
                None if state is None else getattr(state, key),
                CombineReducerInitAction(key=key, _id=_id)
                if isinstance(action, InitAction)
                else action,
            )
            for key, reducer in reducers.items()
        }
        result_state = state_class(
            _id=_id,
            **{
                key: result.state if is_complete_reducer_result(result) else result
                for key, result in reducers_results.items()
            },
        )
        result_actions += functools.reduce(
            operator.iadd,
            [
                result.actions or [] if is_complete_reducer_result(result) else []
                for result in reducers_results.values()
            ],
            [],
        )
        result_events += functools.reduce(
            operator.iadd,
            [
                result.events or [] if is_complete_reducer_result(result) else []
                for result in reducers_results.values()
            ],
            [],
        )

        return CompleteReducerResult(
            state=result_state,
            actions=result_actions,
            events=result_events,
        )

    return combined_reducer, _id
