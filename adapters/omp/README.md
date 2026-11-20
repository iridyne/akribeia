# OMP adapter

This directory connects PCH to the OMP agent runtime used by the author. It is an adapter, not a requirement: the method works with any runtime that can expose session metrics and prompt payloads.

## Files

- `prompt-assert.ts` — an OMP extension loaded with `-e`. It prints one `ASSERT <name>=<true|false>` line per rule that must reach the provider payload. Run it after any rule or prompt-replacement change.
- `../../scripts/collect.py` — a collector loaded with `%load` inside an OMP eval kernel. It pulls session and tool metrics through `session_query` and writes `data/metrics-<date>.json`.

## Prompt assertion probe

```bash
cd /path/to/a/repo/with/AGENTS.md
omp -p "Reply with the single word: ok" --no-title --no-session \
  -e /path/to/pch/adapters/omp/prompt-assert.ts
```

All lines must be `true`. A `false` means the rule is not in the payload; a startup warning about a replacement target means the host prompt drifted. Fix the rule before measuring anything.

## Collect metrics

Inside an OMP eval cell:

```python
%load /path/to/pch/scripts/collect.py
```

The collector uses the sanctioned `session_query` tool, never raw session files. Output stays in `data/`, which is gitignored.

## Notes

- `--no-tools` suppresses the device section of the system prompt, so the `xd://` replacement rule legitimately reports "no target". Use a tools-enabled probe when checking that rule.
- The collector's `eval_file_reads` count is a text heuristic. The weekly reviewer labels incidents; the collector supplies the denominator.