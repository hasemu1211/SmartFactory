# Vision runtime-control pull smoke marker (2026-07-02)

This docs-only marker commit exists to verify that the AI laptop runtime-control
`--git-pull` path reports a real `head_before -> head_after` transition through
`last_result` without changing runtime behavior.

Expected validation target:

- `last_result.git.pull_exit_code == 0`
- `last_result.git.head_before` is the commit before this marker
- `last_result.git.head_after` is this marker commit
- `last_result.status == "succeeded"`
- camera sources may remain offline when hardware is unavailable
