# Playground: daily use as the experiment

The distribution we care about is the author's real work, not a benchmark. That has a cost: no control group, no reset button, and a moving task mix. The method compensates with preregistration, denominators, and explicit confounds.

## 1. Data sources

| Source | What it gives | Access |
|---|---|---|
| OMP session store | sessions, turns, tool calls, errors, status, size | `session_query` inside the agent runtime |
| `omp stats -j` | current-day requests, tokens, cache rate, latency, per-model split | CLI |
| Extension logs | policy hits, pty refusals, injected rules | local logs / session entries |
| Incident reports | the author's own corrections and reflections | manual, with a trace excerpt |

Raw traces stay local. The repository commits aggregates, labels, and redacted excerpts only.

## 2. Metrics

All rates use the same denominator: **sessions started in the window**, unless stated otherwise.

| Metric | Definition | Direction | Guards against |
|---|---|---|---|
| `premature_endings_per_100` | sessions whose final assistant turn ends on tool output or an unmotivated stop | lower | satisficing |
| `eval_file_reads_per_100` | eval calls whose code reads a file or lists a directory | lower | tool-routing violations |
| `tool_error_rate` | errored calls / calls, per tool and overall | lower | interface friction |
| `policy_hit_rate` | blocked or reminded calls / calls | lower, but not zero | over-blocking |
| `turns_per_user_message` | assistant turns / user messages | context-dependent | main-thread doing worker jobs |
| `context_shake_ratio` | results shaken ~x / all results | lower | context pressure |
| `cache_hit_rate` | cache-read tokens / input tokens | higher | prompt instability |
| `one_shot_rate` | user requests completed without a corrective follow-up | higher | rework |

Pair every efficiency metric with a quality metric. Optimizing `premature_endings` alone can produce conclusion-shaped noise.

## 3. Baseline (2026-11-15, measured locally)

These numbers come from the local session-history diagnosis and are a starting point, not a benchmark:

| Metric | Value | Note |
|---|---|---|
| sessions in `--private-tmp--` | 51% | no project identity |
| abnormal session end | 22.7% | status-based |
| tool results shaken | 64% | context pressure |
| bash error rate | 12.3% | tool interface + command quality |
| tool calls per user message | 16 | main thread doing worker jobs |

The baseline is dated. A model change, an extension change, or a workflow change invalidates it; re-measure before comparing.

### Measured baseline (2026-11-20, 14-day window)

Collected through the OMP adapter (`scripts/collect.py`) on the local session store:

| Metric | Value |
|---|---|
| sessions | 51 |
| private-tmp share | 70.6% |
| status | 43 complete, 6 aborted, 1 error, 1 interrupted |
| median assistant turns | 3 |
| bash calls / error rate | 5,437 / 11.05% |
| eval calls / error rate | 1,565 / 6.52% |
| read calls / error rate | 1,827 / 3.72% |
| context shake ratio | 17.69% (6,844 of 38,685 entries) |
| sessions over 5 MB | 9 of 51 |

The 2026-11-15 numbers above used a different measure and window; do not compare them row by row. The current collector cannot measure `eval_file_reads` because the event table stores no code text for eval calls; the weekly reviewer labels those traces.

## 4. What counts as an incident

Log an incident when any of these happens:

- the author corrects the same behavior twice;
- a turn ends without the requested conclusion;
- a rule that exists in the prompt is violated again;
- a tool is used through a forbidden path when a sanctioned path exists;
- a subagent returns a result the orchestrator cannot verify.

Do **not** log every error. A transient tool failure with a successful retry is noise. The incident is the earliest unrecoverable failure, not the loudest symptom.

## 5. Sampling and cadence

- **Weekly** — collect metrics, recompute running experiments, review incidents.
- **Per incident** — localize and label immediately, while the trace is fresh.
- **Per intervention** — preregister, then wait for the sample. No early promotion.
- **Per model change** — mark local evidence `contested` until the experiment is re-run.

## 6. Privacy and redaction

The repository is public. Before writing anything:

- no API keys, tokens, cookies, or auth headers;
- no private IPs, hostnames, or SSH aliases;
- no home-directory paths from a specific machine;
- no raw prompts or file contents;
- no personal names beyond the project's own authorship.

`scripts/audit.py` rejects common key, token, private-IP, and home-path patterns. Redaction is a hard gate, not a review preference.

## 7. Known confounds

- Task mix changes week to week.
- The provider may change a model behind an alias.
- The author learns while the harness changes.
- The weekly reviewer knows which change it proposed.
- Session counts are small; treat 20 sessions as a weak signal, not proof.

Record the confound in the experiment. A result that cannot survive its confounds is a lead, not a claim.
