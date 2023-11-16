# ruff: noqa: A003, D101, D102, D103, D104, D107
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
    ParamSpec,
    Protocol,
    Sequence,
    TypedDict,
    TypeVar,
    cast,
)


@dataclass(frozen=True)
class BaseState:
    ...


class InitializationActionError(Exception):
    def __init__(self: InitializationActionError) -> None:
        super().__init__(
            'The only accepted action type when state is None is "INIT"',
        )


# Type variables
State = TypeVar('State', bound=BaseState)
State_co = TypeVar('State_co', covariant=True)
Action = TypeVar('Action')
SelectorOutput = TypeVar('SelectorOutput')
SelectorOutput_co = TypeVar('SelectorOutput_co', covariant=True)
SelectorOutput_contra = TypeVar('SelectorOutput_contra', contravariant=True)
ComparatorOutput = TypeVar('ComparatorOutput')
ReturnType = TypeVar('ReturnType', bound=Callable[..., None])
Selector = Callable[[State], SelectorOutput]
Comparator = Callable[[State], ComparatorOutput]
ReducerType = Callable[[State | None, Action], State]
AutorunReturnType = TypeVar('AutorunReturnType')
AutorunReturnType_co = TypeVar('AutorunReturnType_co', covariant=True)
P = ParamSpec('P')


@dataclass(frozen=True)
class BaseAction:
    ...


@dataclass(frozen=True)
class InitAction(BaseAction):
    type: Literal['INIT'] = 'INIT'


class Options(TypedDict):
    initial_run: bool | None


class AutorunRunnerParameters(
    Protocol, Generic[SelectorOutput_contra, AutorunReturnType_co]
):
    def __call__(
        self: AutorunRunnerParameters,
        selector_result: SelectorOutput_contra,
    ) -> AutorunReturnType_co:
        ...


class AutorunType(Protocol, Generic[State_co]):
    def __call__(
        self: AutorunType,
        selector: Callable[[State_co], SelectorOutput],
        comparator: Selector | None = None,
    ) -> Callable[
        [AutorunRunnerParameters[SelectorOutput, AutorunReturnType]],
        Callable[[], AutorunReturnType],
    ]:
        ...


@dataclass(frozen=True)
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
    ) -> Callable[[AutorunFunctionParameters], Callable[[], Any]]:
        def decorator(fn: AutorunFunctionParameters) -> Callable[[], Any]:
            last_selector_result: SelectorOutput | None = None
            last_comparator_result: SelectorOutput | None = (
                last_selector_result if comparator is None else None
            )
            last_value: Any | None = None

            def check_and_call(state: State) -> None:
                nonlocal last_selector_result, last_comparator_result, last_value
                selector_result = selector(state)
                if comparator is None:
                    comparator_result = selector_result
                else:
                    comparator_result = cast(SelectorOutput, comparator(state))
                if comparator_result != last_comparator_result:
                    previous_result = last_selector_result
                    last_selector_result = selector_result
                    if len(signature(fn).parameters) == 1:
                        last_value = cast(Callable[[SelectorOutput], ReturnType], fn)(
                            selector_result,
                        )
                    else:
                        last_value = cast(
                            Callable[
                                [SelectorOutput, SelectorOutput | None],
                                ReturnType,
                            ],
                            fn,
                        )(
                            selector_result,
                            previous_result,
                        )

            if options.get('initial_run', True) and state:
                check_and_call(state)

            subscribe(check_and_call)

            return lambda: last_value

        return decorator

    return InitializeStateReturnValue(
        dispatch=dispatch,
        subscribe=subscribe,
        autorun=autorun,
    )


@dataclass(frozen=True)
class CombineReducerActionBase(BaseAction):
    _id: str


@dataclass(frozen=True)
class CombineReducerRegisterActionPayload:
    key: str
    reducer: ReducerType


@dataclass(frozen=True)
class CombineReducerRegisterAction(CombineReducerActionBase):
    payload: CombineReducerRegisterActionPayload
    type: Literal['REGISTER'] = 'REGISTER'


@dataclass(frozen=True)
class CombineReducerUnregisterActionPayload:
    key: str


@dataclass(frozen=True)
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
