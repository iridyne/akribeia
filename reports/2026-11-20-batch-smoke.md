# Batch reviewer smoke test — 2026-11-20

## Purpose

Verify that the weekly reviewer can collect metrics and localize incidents from the live session store **without editing files or opening a PR**. The full weekly job adds the ledger update and draft-PR steps; this test isolates the read-only path.

Command shape:

```bash
omp -p "Read prompts/weekly-review.md. Do not edit files, do not create a branch, do not open a PR. Execute only the collection and localization steps for the last 7 days, then report the metrics and at most 3 incidents in 20 lines or fewer." \
  --no-session --no-title --cwd ~/Projects/proof-carrying-harness
```

Result: completed in 277 seconds, no repository changes.

## Metrics

| Metric | Value |
|---|---|
| sessions | 25 (complete 20, aborted 3, interrupted 1, error 1) |
| sessions under `/tmp` | 21 (84%) |
| assistant turns | median 2, mean 2.6 |
| total size | 40.5 MB; 2 sessions over 5 MB |
| tool calls / errors | 2,801 / 233 (8.3%) |
| bash | 1,109 calls / 136 errors (12.3%) |
| eval | 377 / 31 (8.2%) |
| edit | 172 / 14 (8.1%) |
| read | 612 / 36 (5.9%) |
| context shake | 895 / 10,149 entries (8.8%) |
| eval file I/O | 34 / 377 (9.0%); sampled calls were parsing, build, or remote-path work, not `read` bypass |

Cost is not a 7-day figure: `omp stats -j` covered only 2026-11-20 11:19–12:06 UTC (106 requests, 2.46M input / 155k output, 83.9% cache, 23.3 s average, $0 because the provider is unpriced). Do not report it as a weekly cost.

## Localized incidents

Two incidents were added as `INC-0003` and `INC-0004`.

- **INC-0003** — headline metrics were reported before the placebo control; the control ran only after the user asked. `model-owner · fault: model · satisficing`. Repair proposal: a control-first gate before any metric conclusion (`H-011`, `EXP-0013`).
- **INC-0004** — a congratulatory trade report was parsed back into a new signal, with no message-id deduplication. `model-tool · fault: model · state-tracking failure`. Repair belongs to the downstream project; recorded here because the pattern recurs.

No incident was recorded for the `error` session (SIGHUP after delivery), the `interrupted` session (after a successful commit), or the single-turn `clear`/`ls` sessions: they had no failure evidence. This is the correct behavior — an exit status is not a failure mode.

## What this validates

- The reviewer can use the sanctioned `session_query` path and read the ledgers.
- It localizes to the earliest unrecoverable event instead of the terminal symptom.
- It distinguishes a bad exit status from a task failure.
- It respects the no-edit, no-PR constraint.

## Limits

- Seven days and one user; rates are coarse.
- The `error` status is not a task-failure label.
- The cost window does not match the session window.
- The reviewer is not calibrated yet (`EXP-0012`); its labels are drafts until checked.

## Next

1. Run the full weekly job on its Monday schedule; inspect the first draft PR.
2. Calibrate the reviewer on 20 human-labeled incidents before allowing it to promote a claim.
3. Split bash errors into routing, command, and environment classes.
