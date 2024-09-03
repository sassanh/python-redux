# ruff: noqa: D100, D101, D102, D103, D104, D107
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import replace
from typing import TYPE_CHECKING, Sequence

import pytest
from immutable import Immutable

from redux import (
    BaseAction,
    BaseEvent,
    CompleteReducerResult,
    CreateStoreOptions,
    FinishAction,
    InitAction,
    InitializationActionError,
    ReducerResult,
    Store,
)

if TYPE_CHECKING:
    from redux_pytest.fixtures import StoreSnapshot


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


@pytest.fixture
def store() -> Store:
    # reducer:
    def reducer(
        state: ToDoState | None,
        action: BaseAction,
    ) -> ReducerResult[ToDoState, BaseAction, BaseEvent]:
        if state is None:
            if isinstance(action, InitAction):
                return ToDoState(
                    items=[
                        ToDoItem(
                            id=uuid.uuid4().hex,
                            content='Initial Item',
                            timestamp=time.time(),
                        ),
                    ],
                )
            raise InitializationActionError(action)
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

    return Store(reducer, options=CreateStoreOptions(auto_init=True))


def test_todo(store_snapshot: StoreSnapshot, store: Store) -> None:
    # subscription:
    dummy_render = logging.getLogger().info
    store.subscribe(dummy_render)

    # autorun:
    @store.autorun(
        lambda state: state.items[0].content if len(state.items) > 0 else None,
    )
    def reaction(_: str | None) -> None:
        store_snapshot.take()

    _ = reaction

    # event listener, note that this will run async in a separate thread, so it can
    # include async operations like API calls, etc:
    dummy_api_call = logging.getLogger().info
    store.subscribe_event(CallApi, lambda event: dummy_api_call(event.parameters))

    # dispatch:
    store.dispatch(AddTodoItemAction(content='New Item', timestamp=time.time()))
    store_snapshot.take()

    store.dispatch(FinishAction())
