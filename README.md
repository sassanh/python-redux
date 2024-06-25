# 🎛️ Python Redux

## 🌟 Overview

Python Redux is a Redux implementation for Python, bringing Redux's state management
architecture to Python applications.

### 🔎 Sample Usage

Minimal todo application store implemented using python-redux:

```python
import uuid
from dataclasses import replace
from typing import Sequence

from immutable import Immutable

from redux import (
    BaseAction,
    BaseEvent,
    CompleteReducerResult,
    FinishAction,
    ReducerResult,
)
from redux.main import Store


# state:
class ToDoItem(Immutable):
    id: str
    content: str
    is_done: bool = False


class ToDoState(Immutable):
    items: Sequence[ToDoItem]


# actions:
class AddTodoItemAction(BaseAction):
    content: str


class MarkTodoItemDone(BaseAction):
    id: str


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
                ),
            ],
        )
    if isinstance(action, RemoveTodoItemAction):
        return replace(
            state,
            actions=[item for item in state.items if item.id != action.id],
        )
    if isinstance(action, MarkTodoItemDone):
        return CompleteReducerResult(
            state=replace(
                state,
                items=[
                    replace(item, is_done=True) if item.id == action.id else item
                    for item in state.items
                ],
            ),
            events=[CallApi(parameters={})],
        )
    return state


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


@store.view(lambda state: state.items[0])
def first_item(first_item: ToDoItem) -> ToDoItem:
    return first_item


@store.view(lambda state: [item for item in state.items if item.is_done])
def done_items(done_items: list[ToDoItem]) -> list[ToDoItem]:
    return done_items


# event listener, note that this will run async in a separate thread, so it can include
# io operations like network calls, etc:
dummy_api_call = print
store.subscribe_event(
    CallApi,
    lambda event: dummy_api_call(event.parameters, done_items()),
)

# dispatch:
store.dispatch(AddTodoItemAction(content='New Item'))

store.dispatch(MarkTodoItemDone(id=first_item().id))

store.dispatch(FinishAction())
```

## ⚙️ Features

- Redux API for Python developers.

- Reduce boilerplate by dropping `type` property, payload classes and action creators:

  - Each action is a subclass of `BaseAction`.
  - Its type is checked by utilizing `isinstance` (no need for `type` property).
  - Its payload are its direct properties (no need for a separate `payload` object).
  - Its creator is its auto-generated constructor.

- Use type annotations for all its API.

- Immutable state management for predictable state updates using [python-immutable](https://github.com/sassanh/python-immutable).

- Offers a streamlined, native [API](#handling-side-effects-with-events) for handling
  side-effects asynchronously, eliminating the necessity for more intricate utilities
  such as redux-thunk or redux-saga.

- Incorporates the [autorun decorator](#autorun-decorator) and
  the [view decorator](#view-decorator), inspired by the mobx framework, to better
  integrate with elements of the software following procedural patterns.

- Supports middlewares.

## 📦 Installation

The package handle in PyPI is `python-redux`

### Pip

```bash
pip install python-redux
```

### Poetry

```bash
poetry add python-redux
```

## 🛠 Usage

### Handling Side Effects with Events

Python-redux introduces a powerful concept for managing side effects: **Events**.
This approach allows reducers to remain pure while still signaling the need for
side effects.

#### Why Events?

- **Separation of Concerns**: By returning events, reducers stay pure and focused
  solely on state changes, delegating side effects to other parts of the software.
- **Flexibility**: Events allow asynchronous operations like API calls to be handled
  separately, enhancing scalability and maintainability.

#### How to Use Events

- **Reducers**: Reducers primarily return a new state. They can optionally return
  actions and events, maintaining their purity as these do not enact side effects
  themselves.
- **Dispatch Function**: Besides actions, dispatch function can now accept events,
  enabling a more integrated flow of state and side effects.
- **Event Listeners**: Implement listeners for specific events. These listeners
  handle the side effects (e.g., API calls) asynchronously.

#### Best Practices

- **Define Clear Events**: Create well-defined events that represent specific side
  effects.
- **Use Asynchronously**: Design event listeners to operate asynchronously, keeping
  your application responsive. Note that python-redux, by default, runs all event
  handler functions in new threads.

This concept fills the gap in handling side effects within Redux's ecosystem, offering
a more nuanced and integrated approach to state and side effect management.

See todo sample below or check the [todo demo](/tests/test_todo.py) or
[features demo](/tests/test_features.py) to see it in action.

### Autorun Decorator

Inspired by MobX's [autorun](https://mobx.js.org/reactions.html#autorun) and
[reaction](https://mobx.js.org/reactions.html#reaction), python-redux introduces
the autorun decorator. This decorator requires a selector function as an argument.
The selector is a function that accepts the store instance and returns a derived
object from the store's state. The primary function of autorun is to establish a
subscription to the store. Whenever the store is changed, autorun executes the
selector with the updated store.
Importantly, the decorated function is triggered only if there is a change in the
selector's return value. This mechanism ensures that the decorated function runs
in response to relevant state changes, enhancing efficiency and responsiveness in
the application.

See todo sample below or check the [todo demo](/tests/test_todo.py) or
[features demo](/tests/test_features.py) to see it in action.

### View Decorator

Inspired by MobX's [computed](https://mobx.js.org/computeds.html), python-redux introduces
the view decorator. It takes a selector and each time the decorated function is called,
it only runs the function body if the returned value of the selector is changed,
otherwise it simply returns the previous value. So unlike `computed` of MobX, it
doesn't extract the requirements of the function itself, you need to provide them
in the return value of the selector function.

### Combining reducers - `combine_reducers`

You can compose high level reducers by combining smaller reducers using `combine_reducers`
utility function. This works mostly the same as the JS redux library version except
that it provides a mechanism to dynamically add/remove reducers to/from it.
This is done by generating an id and returning it along the generated reducer.
This id is used to refer to this reducer in the future. Let's assume you composed
a reducer like this:

```python
reducer, reducer_id = combine_reducers(
    state_type=StateType,
    first=straight_reducer,
    second=second_reducer,
)
```

You can then add a new reducer to it using the `reducer_id` like this:

```python
store.dispatch(
    CombineReducerRegisterAction(
        _id=reducer_id,
        key='third',
        third=third_reducer,
    ),
)
```

You can also remove a reducer from it like this:

```python
store.dispatch(
    CombineReducerRegisterAction(
        _id=reducer_id,
        key='second',
    ),
)
```

Without this id, all the combined reducers in the store tree would register `third`
reducer and unregister `second` reducer, but thanks to this `reducer_id`, these
actions will only target the desired combined reducer.

## 🎉 Demo

For a detailed example, see [features demo](/tests/test_features.py).

## 🤝 Contributing

Contributions following Python best practices are welcome.

## 📜 License

This project is released under the Apache-2.0 License. See the [LICENSE](./LICENSE)
file for more details.
