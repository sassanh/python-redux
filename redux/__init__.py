# ruff: noqa: D101, D102, D103, D104, D107
from __future__ import annotations

import uuid
from dataclasses import dataclass
from inspect import signature
from typing import (
    Any,
    Callable,
    Generic,
    Literal,
    Mapping,
    Sequence,
    TypedDict,
    TypeVar,
    cast,
)


class InitializationActionError(Exception):
    def __init__(self: InitializationActionError) -> None:
        super().__init__(
            'The only accepted action type when state is None is "INIT"',
        )


# Type variables
State = TypeVar('State', bound=Mapping[str, Any])
State_co = TypeVar('State_co', covariant=True)
Action = TypeVar('Action')
ParamsType = TypeVar('ParamsType')
ReturnType = TypeVar('ReturnType')
Selector = Callable[[State], Any]
ReducerType = Callable[[State | None, Action], State]


@dataclass
class BaseAction:
    ...


@dataclass
class InitAction(BaseAction):
    type: Literal['INIT'] = 'INIT'


class Options(TypedDict):
    initial_run: bool | None


@dataclass
class InitializeStateReturnValue(Generic[State, Action]):
    dispatch: Callable[[Action | list[Action]], None]
    subscribe: Callable[[Callable[[State], None]], Callable[[], None]]
    autorun: Callable[[Callable[[State], Any]], Callable]


def create_store(
    reducer: ReducerType[State, Action],
    options: Options | None = None,
) -> InitializeStateReturnValue[State, Action]:
    options = options or {'initial_run': True}

    state: State | None = None
    listeners: set[Callable[[State], None]] = set()

    def dispatch(actions: Action | Sequence[Action]) -> None:
        nonlocal state, reducer, listeners
        if not isinstance(actions, Sequence):
            actions = [actions]
        actions = cast(Sequence[Action], actions)
        if len(actions) == 0:
            return
        state = reducer(state, actions[0])
        for action in actions[1:]:
            state = reducer(state, action)
        for listener in listeners:
            listener(state)

    def subscribe(listener: Callable[[State], None]) -> Callable[[], None]:
        nonlocal listeners
        listeners.add(listener)
        return lambda: listeners.remove(listener)

    def autorun(
        selector: Selector,
    ) -> Callable[
        [
            Callable[[ParamsType, ParamsType | None], ReturnType]
            | Callable[[ParamsType], ReturnType],
        ],
        Callable[[ParamsType, ParamsType | None], ReturnType]
        | Callable[[ParamsType], ReturnType],
    ]:
        def decorator(
            fn: Callable[[ParamsType, ParamsType | None], ReturnType]
            | Callable[[ParamsType], ReturnType],
        ) -> (
            Callable[[ParamsType, ParamsType | None], ReturnType]
            | Callable[[ParamsType], ReturnType]
        ):
            last_result: list[ParamsType | None] = [None]

            def check_and_call(state: State) -> None:
                nonlocal last_result
                result = selector(state)
                if result != last_result[0]:
                    previous_result = last_result[0]
                    last_result[0] = result
                    if len(signature(fn).parameters) == 1:
                        cast(Callable[[ParamsType], ReturnType], fn)(
                            result,
                        )
                    else:
                        cast(
                            Callable[[ParamsType, ParamsType | None], ReturnType],
                            fn,
                        )(
                            result,
                            previous_result,
                        )

            if options.get('initial_run', True) and state:
                check_and_call(state)

            subscribe(check_and_call)

            return fn

        return decorator

    return InitializeStateReturnValue(
        dispatch=dispatch,
        subscribe=subscribe,
        autorun=autorun,
    )


@dataclass
class CombineReducerActionBase(BaseAction):
    _id: str


@dataclass
class CombineReducerRegisterActionPayload:
    key: str
    reducer: ReducerType


@dataclass
class CombineReducerRegisterAction(CombineReducerActionBase):
    payload: CombineReducerRegisterActionPayload
    type: Literal['REGISTER'] = 'REGISTER'


@dataclass
class CombineReducerUnregisterActionPayload:
    key: str


@dataclass
class CombineReducerUnregisterAction(CombineReducerActionBase):
    payload: CombineReducerUnregisterActionPayload
    type: Literal['UNREGISTER'] = 'UNREGISTER'


CombineReducerAction = CombineReducerRegisterAction | CombineReducerUnregisterAction


def combine_reducers(
    **reducers: ReducerType,
) -> tuple[ReducerType, str]:
    _id = uuid.uuid4().hex

    def combined_reducer(
        state: State | None,
        action: CombineReducerAction,
    ) -> State:
        if action.type == 'REGISTER' and action._id == _id:
            key = action.payload.key
            reducer = action.payload.reducer
            reducers[key] = reducer
            state = cast(
                State,
                {
                    **(state or {}),
                    key: reducer(
                        None,
                        InitAction(type='INIT'),
                    ),
                },
            )
        if action.type == 'UNREGISTER' and action._id == _id:
            key = action.payload.key
            del reducers[key]
            state = cast(
                State,
                {key_: state[key_] for key_ in reducers if key_ != key}
                if state is not None
                else {},
            )

        return cast(
            State,
            dict(
                _id=_id,
                **{
                    key: reducer(None if state is None else state.get(key), action)
                    for key, reducer in reducers.items()
                },
            ),
        )

    return (combined_reducer, _id)
