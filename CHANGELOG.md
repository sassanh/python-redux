# Changelog

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

- refactor: remove `create_store` closure in favor of `Store` class with identical
  api

## Version 0.9.25

- feat: all subscriptions/listeners with `keep_ref`, now use `WeakMethod` for methods

## Version 0.9.24

- refactor: no error if an unsubscription function is called multiple times

## Version 0.9.23

- feat(combine_reducers): initialization of sub-reducers is done with `CombineReducerInitAction`
  containing `_id` instead of normal `InitAction`

## Version 0.9.22

- fix: `CombineReducerRegisterAction` should take care of `CompleteReducerResult`
  returned by the sub-reducer on its initialization.

## Version 0.9.21

- feat: new option for all subscriptions to hint them keep a weakref of the callback

## Version 0.9.20

- refactor: encapsulate autorun options previously provided as multiple keyword arguments,
  in a single `AutorunOptions` immutable class
- refactor: rename `immediate` to `immediate_run` in autorun subscribers
- feat: default value of `immediate_run` can be set for all subscribers of an autorun
  instance by settings `subscribers_immediate_run` option for the autorun

## Version 0.9.19

- feat: add `immediate` parameter to `subscribe` method of `autorun`'s returned value

## Version 0.9.18

- feat: `autorun` decorator accepts a default value for when store is not initialized
- feat: `autorun` decorator takes its options in its keyword arguments

## Version 0.9.17

- refactor: make `dispatch` accept a `with_state(store)` function as parameter, if
  provided it will dispatch return value of this function

## Version 0.9.15

- refactor: improve typing of `SideEffectRunnerThread`

## Version 0.9.14

- feat: allow `subscribe_event` callback parameter take zero arguments

## Version 0.9.13

- feat: make `subscribe` method of `autorun`'s return value, call its callback with
  the latest value immediately

## Version 0.9.12

- feat: add the latest value of `autorun` to the `value` field of its returned value

## Version 0.9.11

- feat: the provided `scheduler`, if any, should have a `interval` parameter, if
  set to `False`, it should schedule only once, otherwise it should periodically
  call the `callback`

## Version 0.9.10

- feat: `InitializationActionError` shows the incorrect passed action
- refactor: improve typing of autorun's `Comparator`

## Version 0.9.9

- refactor: improve typehints and allow dispatch to get multiple actions/events
  via `*args`

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

- refactor: add `subscribe` property to the type of the return value of an
  autorun decorator

## Version 0.9.2

- refactor: use `Immutable` from python-immutable package (extracted and created
  based on `Immutable` class of this package)

## Version 0.9.1

- refactor: propagate new `FinishEvent` when `FinishAction` is dispatched

## Version 0.9.0

- feat: add `scheduler` option to schedule running actions in the main loop of frameworks
- feat: add `threads` option to run event handlers asynchronous in `threads`
  number of threads
- refacotr: allow `Any` return type for event handler and subscriber functions
- feat: add `subscribe` property to the returned function of `autorun`

## Version 0.8.2

- feat: allow dispatching events with `dispatch` function

## Version 0.8.1

- refactor: postpone nested dispatches

## Version 0.8.0

- feat: drop `type` field in actions and events altogether, recognition is done
  by `isinstance`

## Version 0.7.3

- fix: loosen `subscribe_event` typing constraints as python doesn't have enough
  type narrowing mechanism at the moment

## Version 0.7.2

- fix: add `event_type` to `combine_reducers`

## Version 0.7.0

- feat: replace side effects with events, events being immutable passive data structures

## Version 0.6.4

- fix: let input reducers of `combine_reducers` have arbitrary state types

## Version 0.6.3

- fix: let input reducers of `combine_reducers` have arbitrary action types
  irrelevant to each other

## Version 0.6.2

- fix: let input reducers of `combine_reducers` have arbitrary action types

## Version 0.6.1

- chore: split the project into multiple files
- feat: let reducers return actions and side effects along new state

## Version 0.5.1

- fix: import `dataclass_transform` from `typing_extensions` instead of `typing`

## Version 0.5.0

- feat: introduce `immutable` decorator as a shortcut of
  `dataclass(kw_only=True, frozen=True)`
- feat: introduce `Immutable` class, its subclasses automatically become `immutable`
- refactor: `BaseAction` now inherits from `Immutable`
- refactor: Removed `BaseState`, state classes, payload classes, etc should now
  inherit `Immutable`

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
