# Extracted History

Source: the TeslaBot Git repository, through commit `a159b8c82ed6cbce6fd8e5fec2fcd7a0d93397cb` (October 14, 2026).

The extraction retains 57 commits. The filtered tip before standalone formatting and packaging is `a866a2f`. Author and committer identities, timestamps, and commit messages are retained. Commit hashes change because file trees and ancestry change. Commits with no remaining relevant changes and redundant merges are pruned.

## Projection Rules

- Before TeslaBot commit `ae13b119be7d77d24f5123e674c35d8b8959aa02`, retain the `Validator*` and `Vld*` classes and their supporting definitions from `teslabot/commands.py` as `src/argparsec/parser.py`.
- From that commit onward, retain `teslabot/parser.py` at the same destination. Command dispatch is never included, and there is no historical `commands.py` in this repository.
- Retain only `assert_some`, `round_to_next_second`, `coalesce`, and `map_optional`, plus their required imports and supporting definitions, from each historical `teslabot/utils.py` snapshot as `src/argparsec/utils.py`.
- Map parser unit tests to `tests/test_parser.py`. Before their original separation, select the parser-only test methods from `tests/test_commands.py`, excluding command setup and invocation tests.
- Retain generic sequence tests and parser contract tests. Exclude scheduler and vehicle-command integration tests; replace the sequence test's application-specific validation exception with `ValueError`.
- Rewrite parser test imports to `argparsec.parser` throughout. Preserve historical class names and behavior rather than modernizing earlier revisions.
- Retain `LICENSE.MIT` and its original attribution.

The initial filtered tip's parser implementation was verified byte-for-byte against the source revision. Every retained commit tree was checked against the source projection, every retained Python snapshot was parsed, and pruned commits were checked to have a projection identical to a parent. Earlier snapshots are historical records, not a promise that every revision runs on current Python or has complete standalone packaging.

## Commit Map

`commit-map` records original TeslaBot commit IDs and rewritten IDs produced by `git filter-repo`. An all-zero rewritten ID means that commit was removed. The map covers the extraction only; subsequent formatting and standalone packaging commits have no TeslaBot counterpart.
