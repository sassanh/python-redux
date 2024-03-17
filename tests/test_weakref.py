# ruff: noqa: D100, D101, D102, D103, D104, D107
from __future__ import annotations

import weakref
from dataclasses import replace
from typing import TYPE_CHECKING, Generator

import pytest
from immutable import Immutable

from redux.basic_types import (
    AutorunOptions,
    BaseAction,
    BaseEvent,
    CreateStoreOptions,
    EventSubscriptionOptions,
    FinishAction,
    InitAction,
    InitializationActionError,
)
from redux.main import Store

if TYPE_CHECKING:
    from redux.test import StoreSnapshotContext


class StateType(Immutable):
    value: int


class IncrementAction(BaseAction): ...


class DummyEvent(BaseEvent): ...


def reducer(state: StateType | None, action: IncrementAction | InitAction) -> StateType:
    if state is None:
        if isinstance(action, InitAction):
            return StateType(value=0)
        raise InitializationActionError(action)

    if isinstance(action, IncrementAction):
        return replace(state, value=state.value + 1)
    return state


class AutorunClass:
    def __init__(self: AutorunClass, store_snapshot: StoreSnapshotContext) -> None:
        self.store_snapshot = store_snapshot

    def method_with_keep_ref(self: AutorunClass, value: int) -> int:
        self.store_snapshot.take(title='autorun_method_with_keep_ref')
        return value

    def method_without_keep_ref(self: AutorunClass, _: int) -> int:
        pytest.fail('This should never be called')


class SubscriptionClass:
    def __init__(self: SubscriptionClass, store_snapshot: StoreSnapshotContext) -> None:
        self.store_snapshot = store_snapshot

    def method_with_keep_ref(self: SubscriptionClass, _: StateType) -> None:
        self.store_snapshot.take(title='subscription_method_with_keep_ref')

    def method_without_keep_ref(self: SubscriptionClass, _: StateType) -> None:
        pytest.fail('This should never be called')


class EventSubscriptionClass:
    def __init__(
        self: EventSubscriptionClass,
        store_snapshot: StoreSnapshotContext,
    ) -> None:
        self.store_snapshot = store_snapshot

    def method_with_keep_ref(self: EventSubscriptionClass, _: DummyEvent) -> None:
        self.store_snapshot.take(title='event_subscription_method_with_keep_ref')

    def method_without_keep_ref(self: EventSubscriptionClass, _: DummyEvent) -> None:
        pytest.fail('This should never be called')


@pytest.fixture()
def store() -> (
    Generator[Store[StateType, IncrementAction | InitAction, DummyEvent], None, None]
):
    store = Store(reducer, options=CreateStoreOptions(auto_init=True))
    yield store
    store.dispatch(FinishAction())


def test_autorun(
    store_snapshot: StoreSnapshotContext,
    store: Store[StateType, IncrementAction | InitAction, DummyEvent],
) -> None:
    store_snapshot.set_store(store)

    @store.autorun(lambda state: state.value)
    def render_with_keep_ref(value: int) -> int:
        store_snapshot.take()
        return value

    @store.autorun(
        lambda state: state.value,
        options=AutorunOptions(keep_ref=False, initial_run=False),
    )
    def render_without_keep_ref(_: int) -> int:
        pytest.fail('This should never be called')

    ref = weakref.ref(render_with_keep_ref)
    del render_with_keep_ref
    assert ref() is not None

    ref = weakref.ref(render_without_keep_ref)
    del render_without_keep_ref
    assert ref() is None

    store.dispatch(IncrementAction())


def test_autorun_method(
    store_snapshot: StoreSnapshotContext,
    store: Store[StateType, IncrementAction | InitAction, DummyEvent],
) -> None:
    store_snapshot.set_store(store)

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
        options=AutorunOptions(keep_ref=False, initial_run=False),
    )(
        instance_without_keep_ref.method_without_keep_ref,
    )

    ref = weakref.ref(instance_without_keep_ref)
    del instance_without_keep_ref
    assert ref() is None

    store.dispatch(IncrementAction())


def test_autorun_subscription(
    store_snapshot: StoreSnapshotContext,
    store: Store[StateType, IncrementAction | InitAction, DummyEvent],
) -> None:
    store_snapshot.set_store(store)

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
    store_snapshot: StoreSnapshotContext,
    store: Store[StateType, IncrementAction | InitAction, DummyEvent],
) -> None:
    store_snapshot.set_store(store)

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


def test_subscription(
    store_snapshot: StoreSnapshotContext,
    store: Store[StateType, IncrementAction | InitAction, DummyEvent],
) -> None:
    store_snapshot.set_store(store)

    def subscription_with_keep_ref(_: StateType) -> None:
        store_snapshot.take()

    store.subscribe(subscription_with_keep_ref)
    ref = weakref.ref(subscription_with_keep_ref)
    del subscription_with_keep_ref
    assert ref() is not None

    def subscription_without_keep_ref(_: StateType) -> None:
        pytest.fail('This should never be called')

    store.subscribe(subscription_without_keep_ref, keep_ref=False)
    ref = weakref.ref(subscription_without_keep_ref)
    del subscription_without_keep_ref
    assert ref() is None

    store.dispatch(IncrementAction())


def test_subscription_method(
    store_snapshot: StoreSnapshotContext,
    store: Store[StateType, IncrementAction | InitAction, DummyEvent],
) -> None:
    store_snapshot.set_store(store)

    instance_with_keep_ref = SubscriptionClass(store_snapshot)
    store.subscribe(instance_with_keep_ref.method_with_keep_ref)

    ref = weakref.ref(instance_with_keep_ref)
    del instance_with_keep_ref
    assert ref() is not None

    instance_without_keep_ref = SubscriptionClass(store_snapshot)
    store.subscribe(instance_without_keep_ref.method_without_keep_ref, keep_ref=False)

    ref = weakref.ref(instance_without_keep_ref)
    del instance_without_keep_ref
    assert ref() is None

    store.dispatch(IncrementAction())


def test_event_subscription(
    store_snapshot: StoreSnapshotContext,
    store: Store[StateType, IncrementAction | InitAction, DummyEvent],
) -> None:
    store_snapshot.set_store(store)

    def event_subscription_with_keep_ref(_: DummyEvent) -> None:
        store_snapshot.take()

    store.subscribe_event(
        DummyEvent,
        event_subscription_with_keep_ref,
        options=EventSubscriptionOptions(immediate_run=True),
    )
    ref = weakref.ref(event_subscription_with_keep_ref)
    del event_subscription_with_keep_ref
    assert ref() is not None

    def event_subscription_without_keep_ref(_: DummyEvent) -> None:
        pytest.fail('This should never be called')

    store.subscribe_event(
        DummyEvent,
        event_subscription_without_keep_ref,
        options=EventSubscriptionOptions(keep_ref=False, immediate_run=True),
    )
    ref = weakref.ref(event_subscription_without_keep_ref)
    del event_subscription_without_keep_ref
    assert ref() is None

    store.dispatch(DummyEvent())


def test_event_subscription_method(
    store_snapshot: StoreSnapshotContext,
    store: Store[StateType, IncrementAction | InitAction, DummyEvent],
) -> None:
    store_snapshot.set_store(store)

    instance_with_keep_ref = EventSubscriptionClass(store_snapshot)
    store.subscribe_event(
        DummyEvent,
        instance_with_keep_ref.method_with_keep_ref,
        options=EventSubscriptionOptions(immediate_run=True),
    )

    ref = weakref.ref(instance_with_keep_ref)
    del instance_with_keep_ref
    assert ref() is not None

    instance_without_keep_ref = EventSubscriptionClass(store_snapshot)
    store.subscribe_event(
        DummyEvent,
        instance_without_keep_ref.method_without_keep_ref,
        options=EventSubscriptionOptions(keep_ref=False),
    )

    ref = weakref.ref(instance_without_keep_ref)
    del instance_without_keep_ref
    assert ref() is None

    store.dispatch(DummyEvent())
