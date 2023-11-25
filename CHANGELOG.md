# Changelog

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
