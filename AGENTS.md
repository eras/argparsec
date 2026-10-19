# Project Instructions

## Documentation

- Write documentation, comments, and docstrings about the current version's behavior and API, not the history of changes.
- Avoid historical comparisons such as "no longer", "previously", "now supports", or "after moving". State what the code does and what constraints apply in present-tense terms.

## Downstream notifications

- After pushing updates to the GitHub repository, send local-mail notifications to both `homemau` and `teslabot`. Include the pushed revision, relevant API or behavior changes, verification results, and concrete upgrade or migration instructions. Notify only after a successful push; do not change downstream repositories without authorization.
