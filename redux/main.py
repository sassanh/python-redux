# ruff: noqa: D100, D101, D102, D103, D104, D105, D107
from __future__ import annotations

import queue
import threading
from inspect import signature
from typing import (
    Callable,
    Generic,
    Protocol,
    cast,
)

from .basic_types import (
    Action,
    AutorunReturnType,
    BaseAction,
    ComparatorOutput,
    Immutable,
    ReducerType,
    Selector,
    SelectorOutput,
    SideEffect,
    State,
    State_co,
    is_reducer_result,
    is_state,
)


class CreateStoreOptions(Immutable):
    initial_run: bool = True
    threads: int = 5


class DispatchOptions(Immutable):
    inform_listeners: bool = False


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


class InitializeStateReturnValue(Immutable, Generic[State, Action]):
    dispatch: Callable[[Action | list[Action]], None]
    subscribe: Callable[[Callable[[State], None]], Callable[[], None]]
    autorun: AutorunType[State]


class SideEffectRunnerThread(threading.Thread):
    def __init__(self: SideEffectRunnerThread, task_queue: queue.Queue) -> None:
        super().__init__()
        self.task_queue = task_queue
        self.daemon = True  # Optionally make the thread a daemon

    def run(self: SideEffectRunnerThread) -> None:
        while True:
            # Get a task from the queue
            try:
                task = self.task_queue.get(timeout=3)  # Adjust timeout as needed
            except queue.Empty:
                continue

            try:
                task()  # Execute the task
            finally:
                self.task_queue.task_done()


def create_store(
    reducer: ReducerType[State, Action],
    options: CreateStoreOptions | None = None,
) -> InitializeStateReturnValue[State, Action]:
    _options = CreateStoreOptions() if options is None else options

    state: State
    listeners: set[Callable[[State], None]] = set()
    side_effects_queue: queue.Queue[SideEffect] = queue.Queue()

    for _ in range(_options.threads):
        worker = SideEffectRunnerThread(side_effects_queue)
        worker.start()

    def dispatch(
        actions: Action | list[Action],
        dispatch_options: DispatchOptions | None = None,
    ) -> None:
        dispatch_options = dispatch_options or DispatchOptions(inform_listeners=False)
        nonlocal state, reducer, listeners
        if isinstance(actions, BaseAction):
            actions = [actions]
        if len(actions) == 0:
            return
        actions_queue = list(actions)
        should_quit = False
        while len(actions_queue) > 0:
            action = actions_queue.pop(0)
            result = reducer(state if 'state' in locals() else None, action)
            if is_reducer_result(result):
                state = result.state
                if result.actions:
                    actions_queue.append(*result.actions)
                if result.side_effects:
                    for side_effect in result.side_effects:
                        side_effects_queue.put(side_effect)
            elif is_state(result):
                state = result
            if action.type == 'FINISH':
                should_quit = True

        for listener in listeners:
            listener(state)

        if should_quit:
            side_effects_queue.join()

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
        nonlocal state

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
                        )(selector_result)
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

            if _options.initial_run and state is not None:
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
