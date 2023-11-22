# ruff: noqa: A003, D101, D102, D103, D104, D105, D107
from __future__ import annotations

import copy
import uuid
from dataclasses import asdict, dataclass, make_dataclass
from inspect import signature
from typing import (
    Any,
    Callable,
    Generic,
    Literal,
    Mapping,
    Protocol,
    Sequence,
    TypedDict,
    TypeVar,
    cast,
)

from typing_extensions import dataclass_transform

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


class InitializationActionError(Exception):
    def __init__(self: InitializationActionError) -> None:
        super().__init__(
            'The only accepted action type when state is None is "INIT"',
        )


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
ReducerType = Callable[[State | None, Action], State]
AutorunReturnType = TypeVar('AutorunReturnType')
AutorunReturnType_co = TypeVar('AutorunReturnType_co', covariant=True)


class InitAction(BaseAction):
    type: Literal['INIT'] = 'INIT'


class Options(TypedDict):
    initial_run: bool | None


class AutorunType(Protocol, Generic[State_co]):
    def __call__(
        self: AutorunType,
        selector: Callable[[State_co], SelectorOutput],
        comparator: Selector | None = None,
    ) -> Callable[
        [
            Callable[[SelectorOutput], AutorunReturnType]
            | Callable[[SelectorOutput, SelectorOutput], AutorunReturnType],
        ],
        Callable[[], AutorunReturnType],
    ]:
        ...


@immutable
class InitializeStateReturnValue(Generic[State, Action]):
    dispatch: Callable[[Action | list[Action]], None]
    subscribe: Callable[[Callable[[State], None]], Callable[[], None]]
    autorun: AutorunType[State]


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
        selector: Callable[[State], SelectorOutput],
        comparator: Callable[[State], ComparatorOutput] | None = None,
    ) -> Callable[
        [
            Callable[[SelectorOutput], AutorunReturnType]
            | Callable[[SelectorOutput, SelectorOutput], AutorunReturnType],
        ],
        Callable[[], AutorunReturnType],
    ]:
        def decorator(
            fn: Callable[[SelectorOutput], AutorunReturnType]
            | Callable[[SelectorOutput, SelectorOutput], AutorunReturnType],
        ) -> Callable[[], AutorunReturnType]:
            last_selector_result: SelectorOutput | None = None
            last_comparator_result: ComparatorOutput | None = None
            last_value: AutorunReturnType | None = None

            def check_and_call(state: State) -> None:
                nonlocal last_selector_result, last_comparator_result, last_value
                selector_result = selector(state)
                if comparator is None:
                    comparator_result = cast(ComparatorOutput, selector_result)
                else:
                    comparator_result = comparator(state)
                if comparator_result != last_comparator_result:
                    previous_result = last_selector_result
                    last_selector_result = selector_result
                    last_comparator_result = comparator_result
                    if len(signature(fn).parameters) == 1:
                        last_value = cast(
                            Callable[[SelectorOutput], AutorunReturnType],
                            fn,
                        )(
                            selector_result,
                        )
                    else:
                        last_value = cast(
                            Callable[
                                [SelectorOutput, SelectorOutput | None],
                                AutorunReturnType,
                            ],
                            fn,
                        )(
                            selector_result,
                            previous_result,
                        )

            if options.get('initial_run', True) and state is not None:
                check_and_call(state)

            subscribe(check_and_call)

            def call() -> AutorunReturnType:
                if state is not None:
                    check_and_call(state)
                return cast(AutorunReturnType, last_value)

            return call

        return decorator

    return InitializeStateReturnValue(
        dispatch=dispatch,
        subscribe=subscribe,
        autorun=autorun,
    )


class CombineReducerActionBase(BaseAction):
    _id: str


class CombineReducerRegisterActionPayload(Immutable):
    key: str
    reducer: ReducerType


class CombineReducerRegisterAction(CombineReducerActionBase):
    payload: CombineReducerRegisterActionPayload
    type: Literal['REGISTER'] = 'REGISTER'


class CombineReducerUnregisterActionPayload(Immutable):
    key: str


class CombineReducerUnregisterAction(CombineReducerActionBase):
    payload: CombineReducerUnregisterActionPayload
    type: Literal['UNREGISTER'] = 'UNREGISTER'


CombineReducerAction = CombineReducerRegisterAction | CombineReducerUnregisterAction


def combine_reducers(
    **reducers: ReducerType,
) -> tuple[ReducerType, str]:
    _id = uuid.uuid4().hex

    state_class = make_dataclass(
        'combined_reducer',
        ('_id', *reducers.keys()),
        frozen=True,
        kw_only=True,
    )

    def combined_reducer(
        state: CombineReducerActionBase | None,
        action: CombineReducerAction,
    ) -> CombineReducerActionBase:
        nonlocal state_class
        if state is not None:
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

        return state_class(
            _id=_id,
            **{
                key: reducer(None if state is None else getattr(state, key), action)
                for key, reducer in reducers.items()
            },
        )

    return (combined_reducer, _id)
