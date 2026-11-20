# Ledger

Generated from `claims/`, `mapping/`, `experiments/`, and `incidents/` by `scripts/report.py`.
Do not edit by hand. Run `python3 scripts/report.py --write`.

**Coverage:** 16/16 changes mapped to a claim (100%).

## Literature claims

| ID | Status | Statement | Source |
|---|---|---|---|
| LIT-001 | supported | An agent harness is a runtime layer with four necessary elements: an adaptive loop, a tool interface that alters an environment, active context management, and at least one control mechanism independent of model obedience. | Macedo 2026, What makes a harness a harness |
| LIT-002 | conceptual | Long-horizon agent performance can be organized as a function of reasoning, memory, context construction, skill routing, orchestration, and verification/governance. | Gu 2026, From Model Scaling to System Scaling |
| LIT-003 | supported | Redesigning the agent-computer interface alone, with the model fixed, can substantially change benchmark accuracy. | Yang et al. 2024, SWE-agent |
| LIT-004 | supported | After a model is competently tuned for agency, additional hand-built scaffolding produced modest, non-significant gains in one 195-task study (30% to 38%, 95% CI). | METR 2024, Measuring the impact of post-training enhancements |
| LIT-005 | supported | Plausible prompting and scaffolding changes can make the same model perform noticeably worse. | METR 2024, Measuring the impact of post-training enhancements |
| LIT-006 | supported | A simple three-phase agentless pipeline can outperform more complex agents on SWE-bench Lite at lower cost. | Xia et al. 2024, Agentless |
| LIT-007 | supported | Agent failures are best localized to an interaction edge plus a fault side, using the earliest unrecoverable failure rather than the terminal symptom. | Raj et al. 2026, Model or Harness? |
| LIT-008 | supported | Multi-agent LLM failures cluster into specification issues, inter-agent misalignment, and task verification; prompt-level patches often do not fix them. | Cemri et al. 2025, Why Do Multi-Agent LLM Systems Fail? |
| LIT-009 | supported | Harness policy can be represented as executable natural-language documents that a shared runtime interprets; such harnesses match code/prompt realizations on benchmark tasks and are analyzable by module ablation. | Pan et al. 2026, Natural-Language Agent Harnesses |
| LIT-010 | conceptual | Self-improvement can be formalized as a self-induced update operator on scaffold components (prompt, memory, tools, control), driven by execution, constraint, or exploratory signals. | Ren et al. 2026, Self-Improvements in Modern Agentic Systems |
| LIT-011 | conceptual | Long-horizon agent evaluation should include process metrics (context efficiency, memory hygiene, communication fidelity, verification cost), not only task success. | Gu 2026, From Model Scaling to System Scaling |
| LIT-012 | conceptual | Persistent memory fails in a stale-but-confident mode; trust should be re-established at retrieval against the live environment. | Gu 2026, From Model Scaling to System Scaling |
| LIT-013 | conceptual | Harness configuration varies across releases and runs and should be versioned as part of the system record for reproducibility and comparison. | Towards Portable Specification of the Agent Harness |
| LIT-014 | supported | Longer context does not guarantee access to the relevant information; models attend unevenly across positions, with middle content often underused. | Liu et al. 2024, Lost in the Middle |
| LIT-015 | supported | Prompts and pipeline instructions can be optimized programmatically against a metric, but the result needs a held-out validation set and is vulnerable to overfitting. | Khattab et al. 2023, DSPy |
| LIT-016 | supported | Mixed-initiative interfaces work best when the human specifies goals and constraints, and the system infers when to act, confirm, or defer. | Horvitz 1999, Principles of Mixed-Initiative User Interfaces |

## Local hypotheses

| ID | Status | Statement | Experiment | Falsifier |
|---|---|---|---|---|
| H-001 | hypothesis | A model-agnostic closure rule ('after a tool or probe result, the first sentence is a conclusion; never end a turn on raw tool output') reduces premature endings. | EXP-0001 | No >=25% relative reduction after 20 sessions, or a >=20% increase in turns per user message. |
| H-002 | hypothesis | An explicit permission-escalation path for root-only reads reduces eval file-read violations more than a prohibition alone. | EXP-0002 | No >=25% relative reduction after 20 sessions, or the same violation recurs with a sanctioned path available. |
| H-003 | hypothesis | Delivering a shared rule to main and subagents (target: *) improves adherence compared with delivering it only to the main session. | EXP-0003 | No measurable difference between the two delivery targets after 30 subagent runs. |
| H-004 | hypothesis | For interactive guardrails, deterministic checks beat LLM judges on latency and one-shot completion; LLM judges belong in the weekly batch lane. | EXP-0004 | A judge lane that improves one-shot rate without increasing p95 latency by more than 1 second. |
| H-005 | hypothesis | A weekly batch review catches regressions with acceptable lag and less noise than per-turn review. | EXP-0005 | A regression survives more than two weekly cycles, or more than half of flagged regressions are false alarms. |
| H-006 | hypothesis | For this model class, a rule-layer edit has higher leverage per token than an extension-code change. | EXP-0006 | Extension changes show a larger median effect at equal token cost across five interventions. |
| H-007 | hypothesis | The isolation nudge must treat the local writer roles (task, sonic, hard-task) as writers, or concurrent writes go unreminded. | EXP-0007 | No concurrent-write event in 30 days, or the nudge fires on read-only roles. |
| H-008 | hypothesis | Keeping the native bash interceptor alongside the pty lane reduces routing violations without blocking legitimate commands. | EXP-0008 | False blocks rise above 2% of calls, or the interceptor catches nothing the pty lane misses in 30 days. |
| H-009 | hypothesis | Wording-level prompt replacements that remove a specific ambiguity reduce the corresponding misread without side effects. | EXP-0009 | The misread persists at the same rate after the replacement, or a new misread appears in the same passage. |
| H-010 | hypothesis | A local long-term memory improves recall-dependent tasks without polluting the working context. | EXP-0010 | Recall precision below 50%, or context tokens rise without a reduction in repeated questions. |
| H-011 | hypothesis | A control-first gate before reporting headline metrics reduces premature conclusions in research sessions. | EXP-0013 | No reduction after 10 research reports, or the gate adds more than one turn to every report. |

## Decisions

| ID | Statement | Source |
|---|---|---|
| D-001 | Use a single active configuration. No profiles, no per-project config forks. | owner decision |
| D-002 | No LLM judge in the interactive path. Deterministic checks handle runtime guardrails; LLM judges run only in the weekly batch. | owner decision |
| D-003 | The machine configuration is the source of truth. Upstream repositories are read-only references. | owner decision |
| D-004 | Automated changes are proposed as pull requests. Nothing auto-merges. | owner decision + LIT-016 |
| D-005 | The public repository contains no secrets, no raw prompts, no private hosts, and no home-directory paths. | owner decision |
| D-006 | Prefer deletion over addition at equal evidence. | Ponytail heuristic |
| D-007 | Express model-facing policy as natural-language documents first; use code only for checks that must be deterministic. | LIT-009 |
| D-008 | One variable per experiment. Bundle changes only as exploratory work that cannot promote a claim. | method decision |
| D-009 | Verify target identity before any external or destructive action. | owner decision + LIT-001 |
| D-010 | Version and diff the harness before changing it. | owner decision + LIT-013 |
| D-011 | Volatile facts are date-stamped and re-verified before acting; memory is treated as a hypothesis until checked. | LIT-012 |

## Changes

| ID | Target | Status | Claims | Evidence |
|---|---|---|---|---|
| M-001 | RULES.md:17 | hypothesis | H-002, LIT-007 | EXP-0002 |
| M-002 | RULES.md:32 | hypothesis | H-001, LIT-008 | EXP-0001 |
| M-003 | APPEND-SYSTEM-one-shot.md | hypothesis | H-001, H-003, LIT-009 | EXP-0001, EXP-0003, EXP-0011 |
| M-004 | config.yml:task.prewalk | decision | D-002, LIT-004 |  |
| M-005 | config.yml:ttsr.judge | decision | D-002 |  |
| M-006 | config.yml:task.completionProbe | decision | D-002 |  |
| M-007 | config.yml:security.enabled | decision | D-002 |  |
| M-008 | extensions/isolation-nudge/index.ts:isWriter | hypothesis | H-007, LIT-008 | EXP-0007 |
| M-009 | extensions/tool-policy-nag/index.ts | hypothesis | H-008, LIT-001 | EXP-0008 |
| M-010 | extensions-last/system-prompt-replace/REPLACE-SYSTEM-default.yml | hypothesis | H-009, LIT-003 | EXP-0009 |
| M-011 | extensions/mnemon | hypothesis | H-010, LIT-010, LIT-012 | EXP-0010 |
| M-012 | bin/verify-target.sh | decision | D-009, LIT-001 |  |
| M-013 | bin/omp-config-status.sh | decision | D-010, LIT-013 |  |
| M-014 | docs/network-facts.md | decision | D-011, LIT-012 |  |
| M-015 | extensions/append-system-model/APPEND-SYSTEM-cheap-models.md | decision | D-006, LIT-009 |  |
| M-016 | tests/prompt-assert.ts | decision | D-010, LIT-013 |  |

## Experiments

| ID | Status | Hypothesis | Metric | Falsifier |
|---|---|---|---|---|
| EXP-0001 | running | H-001 | premature_endings_per_100 | No >=25% relative reduction, or turns per user message rises >=20%. |
| EXP-0002 | running | H-002 | eval_file_reads_per_100 | No >=25% relative reduction, or the same violation recurs while a sanctioned path is available. |
| EXP-0003 | planned | H-003 | subagent_rule_violations_per_100 | No measurable difference between arms. |
| EXP-0004 | planned | H-004 | guardrail_latency_p95, false_block_rate, one_shot_rate | The judge lane improves one-shot rate without a >1s p95 latency increase. |
| EXP-0005 | planned | H-005 | regression_detection_lag, false_alarm_rate | A regression survives more than two cycles, or more than half of flags are false alarms. |
| EXP-0006 | planned | H-006 | effect_size_per_1k_prompt_tokens | Code interventions show a larger median effect at equal token cost. |
| EXP-0007 | planned | H-007 | unreminded_concurrent_writes | No concurrent-write event, or the nudge fires on a read-only role. |
| EXP-0008 | planned | H-008 | policy_hit_rate, false_block_rate, tool_error_rate | False blocks >2% of calls, or the interceptor catches nothing the pty lane misses. |
| EXP-0009 | planned | H-009 | targeted_misread_rate | The misread persists at the same rate, or a new misread appears in the same passage. |
| EXP-0010 | planned | H-010 | recall_precision, context_tokens_per_session, repeated_question_rate | Recall precision <50%, or context tokens rise without fewer repeated questions. |
| EXP-0011 | planned | H-001 | premature_endings_per_100 | The on/off difference is smaller than the phase-to-phase variation, or the conclusion shape metric shows no change. |
| EXP-0012 | planned | H-005 | judge_human_kappa, coverage, false_failure_rate | Kappa below 0.6, or the reviewer's flags miss more than 30% of human-flagged failures. |
| EXP-0013 | planned | H-011 | premature_metric_conclusions_per_100 | No reduction, or the gate adds more than one turn to every report. |

## Incidents

| ID | Edge | Fault | Mode | Intervention |
|---|---|---|---|---|
| INC-0001 | model-owner | model | satisficing | M-002, M-003 |
| INC-0002 | model-tool | model | incorrect tool selection | M-001 |
| INC-0003 | model-owner | model | satisficing |  |
| INC-0004 | model-tool | model | state-tracking failure |  |
