# ruff: noqa: A003, D100, D101, D102, D103, D104, D105, D107, T201
from __future__ import annotations

import time
import uuid
from dataclasses import replace
from typing import Sequence

from immutable import Immutable

from redux import BaseAction, Store
from redux.basic_types import (
    BaseEvent,
    CompleteReducerResult,
    FinishAction,
    ReducerResult,
)


# state:
class ToDoItem(Immutable):
    id: str
    content: str
    timestamp: float


class ToDoState(Immutable):
    items: Sequence[ToDoItem]


# actions:
class AddTodoItemAction(BaseAction):
    content: str
    timestamp: float


class RemoveTodoItemAction(BaseAction):
    id: str


# events:
class CallApi(BaseEvent):
    parameters: object


# reducer:
def reducer(
    state: ToDoState | None,
    action: BaseAction,
) -> ReducerResult[ToDoState, BaseAction, BaseEvent]:
    if state is None:
        return ToDoState(
            items=[
                ToDoItem(
                    id=uuid.uuid4().hex,
                    content='Initial Item',
                    timestamp=time.time(),
                ),
            ],
        )
    if isinstance(action, AddTodoItemAction):
        return replace(
            state,
            items=[
                *state.items,
                ToDoItem(
                    id=uuid.uuid4().hex,
                    content=action.content,
                    timestamp=action.timestamp,
                ),
            ],
        )
    if isinstance(action, RemoveTodoItemAction):
        return CompleteReducerResult(
            state=replace(
                state,
                actions=[item for item in state.items if item.id != action.id],
            ),
            events=[CallApi(parameters={})],
        )
    return state


def main() -> None:
    store = Store(reducer)

    # subscription:
    dummy_render = print
    store.subscribe(dummy_render)

    # autorun:
    @store.autorun(
        lambda state: state.items[0].content if len(state.items) > 0 else None,
    )
    def reaction(content: str | None) -> None:
        print(content)

    _ = reaction

    # event listener, note that this will run async in a separate thread, so it can
    # include async operations like API calls, etc:
    dummy_api_call = print
    store.subscribe_event(CallApi, lambda event: dummy_api_call(event.parameters))

    # dispatch:
    store.dispatch(AddTodoItemAction(content='New Item', timestamp=time.time()))

    store.dispatch(FinishAction())
