# Canonical K04 counterfactual evidence

This directory supersedes the earlier probe output whose `before.json` was accidentally
overwritten by a rerun. The canonical command is:

```text
./.venv/bin/python docs/testing/run-20260911-k04-at-most-once/run_evidence.py \
  --output-dir <new-empty-output-dir>
```

The runner creates an isolated temporary source tree, restores only the historical
`prepare_invocation` implementation there, and runs the same counted probe against that
counterfactual and the repaired working-tree source. Each output directory is created
exclusively and the probe output file is opened with exclusive creation.

- `before.json`: known bad counterfactual, `generate_calls=2`, exit 1.
- `after.json`: repaired candidate, `generate_calls=1`, full durable responses identical,
  exit 0.
- `manifest.json`: source hashes, commands, exits and scope.

This proves the L1 same-process concurrent graph-duplication slice. It does not close
crash recovery, cross-process ownership, SSE cross-entry replay, or business side effects.
