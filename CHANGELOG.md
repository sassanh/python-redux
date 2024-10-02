# Changelog

## Version 0.17.0

- refactor(autorun): remove `auto_call` option as it was addressing such a rare use case that it was not worth the complexity

## Version 0.16.1

- feat(core): add `_type` field to the serialized immutable instances

## Version 0.16.0

- feat(core): add blocking `wait_for_event_handlers` method to `Store` to wait for all event handlers to finish

## Version 0.15.10

- feat(test): add arguments for `wait_for`'s `check`

## Version 0.15.9

- refactor(core): use `str_to_bool` of `python-strtobool` instead of `strtobool` of `distutils`
- feat(test-snapshot): add prefix to snapshot fixture

## Version 0.15.8

- feat(test-snapshot): the `selector` function can signal the `monitor` it should ignore a particular snapshot of the state by returning `None`

## Version 0.15.7

- refactor(test-snapshot): make it aligned with `pyfakefs` by using `try`/`except` instead of checking `Path().exists()` as `pyfakefs` doesn't seem to respect `skip_names` for `Path().exists()`

## Version 0.15.5

- feat(test-snapshot): while still taking snapshots of the whole state of the store, one can narrow this down by providing a selector to the `snapshot` method (used to be a property)
- feat(test-snapshot): new `monitor` method to let a test automatically take snapshots of the store whenever it is changed. Takes an optional selector to narrow down the snapshot.

## Version 0.15.4

- build(pypi): add metadata

## Version 0.15.3

- docs: add an introduction of `view` to `README.md`

## Version 0.15.2

- refactor(autorun): improve type-hints so that its final return value has the correct type, regardless `default_value` is provided or not
- refactor(view): improve type-hints so that its final return value has the correct type, regardless `default_value` is provided or not
- refactor(combine_reducers): use `make_immutable` instead of `make_dataclass`
- test(view): write tests for `store.view`

## Version 0.15.1

- feat(core): add `view` method to `Store` to allow computing a derived value from the state only when it is accessed and caching the result until the relevant parts of the state change
- feat(test): add performance tests to check it doesn't timeout in edge cases

## Version 0.15.0

- refactor(autorun)!: setting `initial_run` option of autorun to `False` used to make the autorun simply not call the function on initialization, now it makes sure the function is not called until the selector's value actually changes
- feat(autorun): add `auto_call` and `reactive` options to autorun to control whether the autorun should call the function automatically when the comparator's value changes and whether it shouldn't automatically call it but yet register a change so that when it is manually called the next time, it will call the function.

## Version 0.14.5

- test(middleware): add middleware tests

## Version 0.14.4

- refactor(test): add the counter id of the failed snapshot to the error message

## Version 0.14.3

- fix: add `unsubscribe` method to `AutorunReturnType` protocol

## Version 0.14.2

- refactor: middleware functions can now return `None` to cancel an action or event

## Version 0.14.1

- feat: introduce `grace_time_in_seconds` parameter to `Store` to allow a grace period for the store to finish its work before calling `cleanup` and `on_finish`

## Version 0.14.0

- refactor: `Store` no longer aggregates changes, it now calls listeners with every change
- refactor: `SideEffectRunnerThread` now runs async side effects in the event loop of the thread in which it was instantiated in (it used to create its own event loop)
- refactor(test): `event_loop` fixture now sets the global event loop on setup and restores it on teardown

## Version 0.13.2

- fix: initial snapshot cleanup which used to mistakenly remove files with store:... filenames now removes files with store-... filenames

## Version 0.13.1

- chore: changed the format of snapshot filenames from store:... to store-...

## Version 0.13.0

- chore(test): move fixtures and testing utilities to `redux-pytest` package
- feat(test): add `wait_for`, `store_monitor`, `event_loop` and `needs_finish` fixtures
- test: add tests for scheduler and fixtures
- refactor: `SideEffectRunnerThread` now runs async side effects in its own event-loop
- refactor: removed `immediate_run` from event subscriptions
- refactor: removed `EventSubscriptionOptions` as the only option left was `keep_ref`, it's now a parameter of `subscribe_event`
- feat: new `on_finish` callback for the store, it runs when all worker threads are joined and resources are freed

## Version 0.12.7

- fix: automatically unsubscribe autoruns when the weakref is dead
- fix: use weakref of event handlers in `event_handlers_queue`

## Version 0.12.6

- refactor: drop logging fixture and use standard pytest logger in tests

## Version 0.12.5

- refactor: add cleanup to `FinishEvent` handler to clean workers, listeners, subscriptions, autoruns, etc
- refactor: `TaskCreator` add `TaskCreatorCallback` protocols
- refactor: `Store._create_task` now has a callback parameter to report the created task
- refactor: move serialization methods and side_effect_runner class to separate files

## Version 0.12.4

- fix: serialization class methods of `Store` use `cls` instead of `Store` for the sake of extensibility via inheritance
- refactor: `pytest_addoption` moved to `test.py` to make reusable

## Version 0.12.3

- test: write tests for different features of the api
- refactor: rename certain names in the api to better reflect their job
- refactor: store_snapshot now puts snapshot files in a hierarchical directory structure based on the test module and test name
- fix: sort JSON keys in `snapshot_store`'s `json_snapshot`
- test: cover most features with tests

## Version 0.12.2

- docs: update path of demos migrated to tests in `README.md`
- refactor: remove `set_customer_serializer` in favor of overridable `serialize_value`

## Version 0.12.1

- refactor: move store serializer from test framework to code `Store` class
- feat: add ability to set custom serializer for store snapshots

## Version 0.12.0

- refactor: improve creating new state classes in `combine_reducers` upon registering/unregistering sub-reducers
- feat: add test fixture for snapshot testing the store
- chore(test): add test infrastructure for snapshot testing the store
- test: move demo files to test files and update the to use snapshot fixture

## Version 0.11.0

- feat: add `keep_ref` parameter to subscriptions and autoruns, defaulting to `True`, if set to `False`, the subscription/autorun will not keep a reference to the callback
- refacotr: general housekeeping

## Version 0.10.7

- fix: autorun now correctly updates its value when the store is updated
- feat: add `__repr__` to `Autorun` class

## Version 0.10.6

- chore: improve github workflow caching

## Version 0.10.5

- fix: `self_workers` in `Store.__init__` -> local variable `workers`

## Version 0.10.4

- chore: GitHub workflow to publish pushes on `main` branch to PyPI
- chore: create GitHub release for main branch in GitHub workflows
- refactor: fix lint issues and typing issues

## Version 0.10.0

- refactor: remove `create_store` closure in favor of `Store` class with identical api

## Version 0.9.25

- feat: all subscriptions/listeners with `keep_ref`, now use `WeakMethod` for methods

## Version 0.9.24

- refactor: no error if an unsubscription function is called multiple times

## Version 0.9.23

- feat(combine_reducers): initialization of sub-reducers is done with `CombineReducerInitAction` containing `_id` instead of normal `InitAction`

## Version 0.9.22

- fix: `CombineReducerRegisterAction` should take care of `CompleteReducerResult` returned by the sub-reducer on its initialization.

## Version 0.9.21

- feat: new option for all subscriptions to hint them keep a weakref of the callback

## Version 0.9.20

- refactor: encapsulate autorun options previously provided as multiple keyword arguments, in a single `AutorunOptions` immutable class
- refactor: rename `immediate` to `immediate_run` in autorun subscribers
- feat: default value of `immediate_run` can be set for all subscribers of an autorun instance by settings `subscribers_immediate_run` option for the autorun

## Version 0.9.19

- feat: add `immediate` parameter to `subscribe` method of `autorun`'s returned value

## Version 0.9.18

- feat: `autorun` decorator accepts a default value for when store is not initialized
- feat: `autorun` decorator takes its options in its keyword arguments

## Version 0.9.17

- refactor: make `dispatch` accept a `with_state(store)` function as parameter, if provided it will dispatch return value of this function

## Version 0.9.15

- refactor: improve typing of `SideEffectRunnerThread`

## Version 0.9.14

- feat: allow `subscribe_event` callback parameter take zero arguments

## Version 0.9.13

- feat: make `subscribe` method of `autorun`'s return value, call its callback with the latest value immediately

## Version 0.9.12

- feat: add the latest value of `autorun` to the `value` field of its returned value

## Version 0.9.11

- feat: the provided `scheduler`, if any, should have a `interval` parameter, if set to `False`, it should schedule only once, otherwise it should periodically call the `callback`

## Version 0.9.10

- feat: `InitializationActionError` shows the incorrect passed action
- refactor: improve typing of autorun's `Comparator`

## Version 0.9.9

- refactor: improve typehints and allow dispatch to get multiple actions/events via `*args`

## Version 0.9.8

- feat: autorun now recovers from selector attribute errors = uninitialized store

## Version 0.9.7

- docs: explain events in more details in `README.md`

## Version 0.9.6

- docs: add `README.md`

## Version 0.9.5

- refactor: remove `payload` and `...Payload` classes from `combine_reducers`

## Version 0.9.4

- refactor: actions and events are queued solely via `dispatch` function, even internally
- feat: add `action_middleware` and `event_middleware` fields to `CreateStoreOptions`

## Version 0.9.3

- refactor: add `subscribe` property to the type of the return value of an autorun decorator

## Version 0.9.2

- refactor: use `Immutable` from python-immutable package (extracted and created based on `Immutable` class of this package)

## Version 0.9.1

- refactor: propagate new `FinishEvent` when `FinishAction` is dispatched

## Version 0.9.0

- feat: add `scheduler` option to schedule running actions in the main loop of frameworks
- feat: add `threads` option to run event handlers asynchronous in `threads` number of threads
- refacotr: allow `Any` return type for event handler and subscriber functions
- feat: add `subscribe` property to the returned function of `autorun`

## Version 0.8.2

- feat: allow dispatching events with `dispatch` function

## Version 0.8.1

- refactor: postpone nested dispatches

## Version 0.8.0

- feat: drop `type` field in actions and events altogether, recognition is done by `isinstance`

## Version 0.7.3

- fix: loosen `subscribe_event` typing constraints as python doesn't have enough type narrowing mechanism at the moment

## Version 0.7.2

- fix: add `event_type` to `combine_reducers`

## Version 0.7.0

- feat: replace side effects with events, events being immutable passive data structures

## Version 0.6.4

- fix: let input reducers of `combine_reducers` have arbitrary state types

## Version 0.6.3

- fix: let input reducers of `combine_reducers` have arbitrary action types irrelevant to each other

## Version 0.6.2

- fix: let input reducers of `combine_reducers` have arbitrary action types

## Version 0.6.1

- chore: split the project into multiple files
- feat: let reducers return actions and side effects along new state

## Version 0.5.1

- fix: import `dataclass_transform` from `typing_extensions` instead of `typing`

## Version 0.5.0

- feat: introduce `immutable` decorator as a shortcut of `dataclass(kw_only=True, frozen=True)`
- feat: introduce `Immutable` class, its subclasses automatically become `immutable`
- refactor: `BaseAction` now inherits from `Immutable`
- refactor: Removed `BaseState`, state classes, payload classes, etc should now inherit `Immutable`

## Version 0.4.0

- refactor: make all dataclasses `kw_only=True`

## Version 0.3.4

- refactor: support previous_result argument, improve typings

## Version 0.3.3

- refactor: improve typings

## Version 0.3.2

- fix: autorun should re-compute the value if it is expired

## Version 0.3.1

- fix: last_comparator_result wasn't being updated

## Version 0.3.0

- feat: add cached return value to autorun
- feat: improve typing

## Version 0.2.0

- feat: make states and action immutable dataclasses

## Version 0.1.0

- feat: implement demo covering autorun, subscription and combining reducers
- feat: implement combine_reducers
- feat: implement autorun
- feat: initial implementation
