# ruff: noqa: D100, D101, D102, D103, D107
from __future__ import annotations

import weakref
from dataclasses import replace
from typing import TYPE_CHECKING, TypeAlias

import pytest
from immutable import Immutable

from redux.basic_types import (
    AutorunOptions,
    BaseAction,
    BaseEvent,
    FinishAction,
    FinishEvent,
    InitAction,
    InitializationActionError,
    StoreOptions,
)
from redux.main import Store
from redux.side_effect_runner import SideEffectRunner

if TYPE_CHECKING:
    from collections.abc import Generator

    from pytest_mock import MockerFixture

    from redux_pytest.fixtures import StoreSnapshot, WaitFor
    from redux_pytest.fixtures.event_loop import LoopThread


class StateType(Immutable):
    value: int


class IncrementAction(BaseAction): ...


class DummyEvent(BaseEvent): ...


StoreType: TypeAlias = Store[
    StateType,
    IncrementAction | InitAction,
    DummyEvent | FinishEvent,
]


def reducer(state: StateType | None, action: IncrementAction | InitAction) -> StateType:
    if state is None:
        if isinstance(action, InitAction):
            return StateType(value=0)
        raise InitializationActionError(action)

    if isinstance(action, IncrementAction):
        return replace(state, value=state.value + 1)
    return state


class AutorunClass:
    def __init__(self: AutorunClass, store_snapshot: StoreSnapshot) -> None:
        self.store_snapshot = store_snapshot

    def method_with_keep_ref(self: AutorunClass, value: int) -> int:
        self.store_snapshot.take(title='autorun_method_with_keep_ref')
        return value

    def method_without_keep_ref(self: AutorunClass, _: int) -> None:
        pytest.fail('This should never be called')


class SubscriptionClass:
    def __init__(self: SubscriptionClass, store_snapshot: StoreSnapshot) -> None:
        self.store_snapshot = store_snapshot

    def method_with_keep_ref(self: SubscriptionClass, _: StateType) -> None:
        self.store_snapshot.take(title='subscription_method_with_keep_ref')

    def method_without_keep_ref(self: SubscriptionClass, _: StateType) -> None:
        pytest.fail('This should never be called')


class EventSubscriptionClass:
    def __init__(
        self: EventSubscriptionClass,
        store_snapshot: StoreSnapshot,
    ) -> None:
        self.store_snapshot = store_snapshot

    def method_with_keep_ref(self: EventSubscriptionClass, _: DummyEvent) -> None:
        self.store_snapshot.take(title='event_subscription_method_with_keep_ref')

    def method_without_keep_ref(self: EventSubscriptionClass, _: DummyEvent) -> None:
        pytest.fail('This should never be called')


@pytest.fixture
def store(event_loop: LoopThread) -> Generator[StoreType, None, None]:
    store = Store(
        reducer,
        options=StoreOptions(
            auto_init=True,
            task_creator=event_loop.create_task,
        ),
    )
    yield store
    store.subscribe_event(FinishEvent, lambda: event_loop.stop())
    store.dispatch(FinishAction())


def test_autorun(
    store: StoreType,
    store_snapshot: StoreSnapshot,
    wait_for: WaitFor,
) -> None:
    @wait_for
    def check_initial_state() -> None:
        assert store._state is not None  # noqa: SLF001

    check_initial_state()

    @store.autorun(lambda state: state.value)
    def render_with_keep_ref(value: int) -> int:
        store_snapshot.take()
        return value

    @store.autorun(
        lambda state: state.value,
        options=AutorunOptions(keep_ref=False, initial_call=False),
    )
    def render_without_keep_ref(_: int) -> None:
        pytest.fail('This should never be called')

    ref = weakref.ref(render_with_keep_ref)
    del render_with_keep_ref
    assert ref() is not None

    ref = weakref.ref(render_without_keep_ref)
    del render_without_keep_ref

    @wait_for
    def check_no_ref() -> None:
        assert ref() is None

    check_no_ref()

    store.dispatch(IncrementAction())


def test_autorun_method(
    store_snapshot: StoreSnapshot,
    store: StoreType,
) -> None:
    instance_with_keep_ref = AutorunClass(store_snapshot)
    store.autorun(lambda state: state.value)(
        instance_with_keep_ref.method_with_keep_ref,
    )

    ref = weakref.ref(instance_with_keep_ref)
    del instance_with_keep_ref
    assert ref() is not None

    instance_without_keep_ref = AutorunClass(store_snapshot)
    store.autorun(
        lambda state: state.value,
        options=AutorunOptions(keep_ref=False, initial_call=False),
    )(
        instance_without_keep_ref.method_without_keep_ref,
    )

    ref = weakref.ref(instance_without_keep_ref)
    del instance_without_keep_ref
    assert ref() is None

    store.dispatch(IncrementAction())


def test_autorun_subscription(
    store_snapshot: StoreSnapshot,
    store: StoreType,
) -> None:
    @store.autorun(lambda state: state.value)
    def render(value: int) -> int:
        store_snapshot.take()
        return value

    def autorun_subscription_with_keep_ref(_: int) -> None:
        store_snapshot.take(title='autorun_subscription')

    render.subscribe(autorun_subscription_with_keep_ref)
    ref = weakref.ref(autorun_subscription_with_keep_ref)
    del autorun_subscription_with_keep_ref
    assert ref() is not None

    def autorun_subscription_without_keep_ref(_: int) -> None:
        pytest.fail('This should never be called')

    render.subscribe(
        autorun_subscription_without_keep_ref,
        keep_ref=False,
        initial_run=False,
    )
    ref = weakref.ref(autorun_subscription_without_keep_ref)
    del autorun_subscription_without_keep_ref
    assert ref() is None

    store.dispatch(IncrementAction())


def test_autorun_method_subscription(
    store_snapshot: StoreSnapshot,
    store: StoreType,
) -> None:
    @store.autorun(lambda state: state.value)
    def render(value: int) -> int:
        store_snapshot.take()
        return value

    instance_with_keep_ref = AutorunClass(store_snapshot)
    render.subscribe(instance_with_keep_ref.method_with_keep_ref)

    ref = weakref.ref(instance_with_keep_ref)
    del instance_with_keep_ref
    assert ref() is not None

    instance_without_keep_ref = AutorunClass(store_snapshot)
    render.subscribe(
        instance_without_keep_ref.method_without_keep_ref,
        keep_ref=False,
        initial_run=False,
    )

    ref = weakref.ref(instance_without_keep_ref)
    del instance_without_keep_ref
    assert ref() is None

    store.dispatch(IncrementAction())


def test_subscription(store: StoreType) -> None:
    with_ref_counter = []

    def subscription_with_keep_ref(_: StateType) -> None:
        with_ref_counter.append(None)

    store._subscribe(subscription_with_keep_ref)  # noqa: SLF001

    ref = weakref.ref(subscription_with_keep_ref)
    del subscription_with_keep_ref
    assert ref() is not None

    without_ref_counter = []

    def subscription_without_keep_ref(_: StateType) -> None:
        without_ref_counter.append(None)

    store._subscribe(subscription_without_keep_ref, keep_ref=False)  # noqa: SLF001

    store.dispatch(IncrementAction())

    ref = weakref.ref(subscription_without_keep_ref)
    del subscription_without_keep_ref
    assert ref() is None

    store.dispatch(IncrementAction())

    assert len(with_ref_counter) == 2
    assert len(without_ref_counter) == 1


def test_subscription_method(
    store_snapshot: StoreSnapshot,
    store: StoreType,
) -> None:
    instance_with_keep_ref = SubscriptionClass(store_snapshot)
    store._subscribe(instance_with_keep_ref.method_with_keep_ref)  # noqa: SLF001

    ref = weakref.ref(instance_with_keep_ref)
    del instance_with_keep_ref
    assert ref() is not None

    instance_without_keep_ref = SubscriptionClass(store_snapshot)
    store._subscribe(instance_without_keep_ref.method_without_keep_ref, keep_ref=False)  # noqa: SLF001

    ref = weakref.ref(instance_without_keep_ref)
    del instance_without_keep_ref
    assert ref() is None

    store.dispatch(IncrementAction())


def test_event_subscription(
    store: StoreType,
    wait_for: WaitFor,
    mocker: MockerFixture,
) -> None:
    event_subscription_with_keep_ref = mocker.stub()

    store.subscribe_event(
        DummyEvent,
        event_subscription_with_keep_ref,
    )
    ref1 = weakref.ref(event_subscription_with_keep_ref)
    del event_subscription_with_keep_ref
    assert ref1() is not None

    def event_subscription_without_keep_ref(_: DummyEvent) -> None:
        pytest.fail('This should never be called')

    store.subscribe_event(
        DummyEvent,
        event_subscription_without_keep_ref,
        keep_ref=False,
    )
    ref2 = weakref.ref(event_subscription_without_keep_ref)
    del event_subscription_without_keep_ref
    assert ref2() is None

    store._dispatch([DummyEvent()])  # noqa: SLF001

    @wait_for
    def subscriptions_ran() -> None:
        event_subscription_with_keep_ref = ref1()
        assert event_subscription_with_keep_ref is not None
        event_subscription_with_keep_ref.assert_called_once_with(DummyEvent())

    subscriptions_ran()


def test_event_subscription_method(
    store_snapshot: StoreSnapshot,
    store: StoreType,
    wait_for: WaitFor,
    mocker: MockerFixture,
) -> None:
    instance_with_keep_ref = EventSubscriptionClass(store_snapshot)
    instance_with_keep_ref.method_with_keep_ref = mocker.spy(
        instance_with_keep_ref,
        'method_with_keep_ref',
    )
    store.subscribe_event(
        DummyEvent,
        instance_with_keep_ref.method_with_keep_ref,
    )

    mocked_method_ref = weakref.ref(instance_with_keep_ref.method_with_keep_ref)
    ref = weakref.ref(instance_with_keep_ref)
    del instance_with_keep_ref
    assert ref() is not None

    instance_without_keep_ref = EventSubscriptionClass(store_snapshot)
    store.subscribe_event(
        DummyEvent,
        instance_without_keep_ref.method_without_keep_ref,
        keep_ref=False,
    )

    ref = weakref.ref(instance_without_keep_ref)
    del instance_without_keep_ref
    assert ref() is None

    store._dispatch([DummyEvent()])  # noqa: SLF001

    @wait_for
    def subscriptions_ran() -> None:
        method = mocked_method_ref()
        assert method is not None
        method.assert_called_once_with(DummyEvent())

    subscriptions_ran()


def test_event_subscription_with_ref_no_keep_ref(
    store: StoreType,
    wait_for: WaitFor,
    mocker: MockerFixture,
) -> None:
    # Create a handler that we will keep alive ourselves
    handler = mocker.stub()

    # Subscribe with keep_ref=False
    store.subscribe_event(
        DummyEvent,
        handler,
        keep_ref=False,
    )

    # Dispatch event
    store._dispatch([DummyEvent()])  # noqa: SLF001

    # Check if handler was called
    @wait_for
    def subscriptions_ran() -> None:
        handler.assert_called_once_with(DummyEvent())

    subscriptions_ran()


def test_event_subscription_with_dead_ref(
    wait_for: WaitFor,
) -> None:
    import queue
    import threading

    task_queue = queue.Queue()
    runner = SideEffectRunner(task_queue=task_queue, create_task=None)
    runner.start()

    # Create a dead weakref
    class Handler:
        pass

    h = Handler()
    ref = weakref.ref(h)
    del h

    # assert dead
    assert ref() is None

    # Put into queue
    task_queue.put((ref, DummyEvent()))

    # Put a sentinel to know it processed
    completed = threading.Event()

    def sentinel(_: DummyEvent) -> None:
        completed.set()

    task_queue.put((sentinel, DummyEvent()))

    @wait_for
    def done() -> None:
        assert completed.is_set()

    done()

    task_queue.put(None)  # stop
    runner.join()


def test_event_subscription_with_live_ref(
    wait_for: WaitFor,
    mocker: MockerFixture,
) -> None:
    """Test that SideEffectRunner correctly dereferences live weakrefs."""
    import queue

    task_queue = queue.Queue()
    runner = SideEffectRunner(task_queue=task_queue, create_task=None)
    runner.start()

    # Create a handler and keep it alive
    handler = mocker.stub()
    ref = weakref.ref(handler)

    # The weakref is alive
    assert ref() is not None

    # Put the weakref (not the handler directly) into the queue
    task_queue.put((ref, DummyEvent()))

    @wait_for
    def handler_called() -> None:
        handler.assert_called_once_with(DummyEvent())

    handler_called()

    task_queue.put(None)  # stop
    runner.join()
