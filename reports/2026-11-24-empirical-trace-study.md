# Empirical Study: Heavy-Coding Agent Trace Telemetry (2026-09-01 to 2026-11-23)

> **Status:** Local observational evidence (`analyze_traces.py`, aggregates only; zero raw prompts or paths stored).  
> **Reproduce format on public synthetic fixture:** `python3 scripts/analyze_traces.py examples/demo-sessions --markdown`

## 1. Corpus & Denominators

Collected from the local OMP coding-agent session store (`2026-09-01` through `2026-11-23`, `min_turns=1`):

| Metric | Measured Value | Notes |
|---|---:|---|
| Sessions analyzed | **995** | 700 named-project (70.4%), 295 ephemeral `--private-tmp--` (29.6%) |
| Heavy long-horizon sessions (`>= 10` turns) | **716** (72.0%) | Median 43.0 turns; carries **114,390 / 116,129 (98.5%)** of all tool calls |
| Assistant turns distribution | P50 **23.0** / P90 **233.8** / P99 **1,351.8** | 63 sessions exceed 5 MB on disk |
| Total context volume (chars) | **442,753,803** | Tool outputs **70.8%**, assistant **26.8%**, user **2.3%** |
| Per-session tool-output share | **60.2%** | 95% bootstrap CI `[58.2%, 62.4%]` (1,000 resamples, seed 42) |
| Context-shake entries | **28,757 / 386,919** (**7.43%**) | Entries compressed/shaken under context pressure |
| Total prompt tokens | **19,210,577,188** | Pooled prompt-cache hit rate **71.03%**; total output tokens 57.6M |
| Tool calls / errors | **116,129 / 6,385** (**5.50%**) | Per-session mean error rate (where calls > 0) |

## 2. Stratification: Heavy vs. Short & Project Identity

| Cohort | Sessions | Median turns | Tool calls | Tool error rate | Tool output share | Pooled cache hit | Abort rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| Heavy (`>= 10` turns) | 716 | 43.0 | 114,390 | **5.52%** | 70.7% | **71.1%** | **32.5%** |
| Short (`< 10` turns) | 279 | 2.0 | 1,739 | 3.80% | 74.1% | 24.7% | 14.7% |
| Named project | 700 | 27.0 | 90,337 | **4.81%** | 74.6% | 68.3% | **25.1%** |
| Ephemeral (`--private-tmp--`) | 295 | 11.0 | 25,792 | **7.91%** | 50.3% | 81.9% | **33.2%** |

## 3. Tool-Interface Failure Surface (116,129 Calls)

| Tool | Calls | Errors | Error rate | Share of tool-output chars |
|---|---:|---:|---:|---:|
| `bash` | 37,528 | 3,538 | **9.43%** | 10.9% |
| `eval` | 28,999 | 1,521 | 5.25% | **57.3%** |
| `read` | 20,181 | 382 | **1.89%** | 18.9% |
| `grep` | 7,537 | 115 | **1.53%** | 7.9% |
| `todo` | 6,214 | 81 | 1.30% | 1.4% |
| `edit` | 6,160 | 411 | **6.67%** | 0.9% |
| `write` | 3,869 | 78 | 2.02% | 1.1% |
| `glob` | 1,690 | 110 | 6.51% | 0.3% |
| `web_search` | 1,313 | 7 | 0.53% | 0.8% |
| `wait` | 808 | 46 | 5.69% | 0.2% |
| `yield` | 406 | 26 | 6.40% | 0.0% |
| `task` | 238 | 13 | 5.46% | 0.0% |

## 4. Key Findings & Explicit Confounds

1. **Tool outputs dominate the context budget (70.8% pooled; 95% CI `[58.2%, 62.4%]` per session).** User prompts account for only 2.3% of raw characters. Over half of all tool-output volume (`57.3%`) originates from `eval` responses, making tool-output truncation and progressive skill/context loading far higher leverage than shortening user instructions.
2. **Structured ACI tools fail 5–6× less often than unconstrained shell (`LIT-003` corroboration).** `bash` fails at **9.43%** (`3,538 / 37,528`) versus structured `read` at **1.89%** and `grep` at **1.53%**. `edit` (`6.67%`) is the second highest-friction core coding tool, reflecting search-replace drift in large files.
3. **Missing project identity correlates with +64% higher tool error rate.** Sessions in `--private-tmp--` (no repository root, no repo rules) exhibit **7.91%** tool errors and **33.2%** aborts versus **4.81%** tool errors and **25.1%** aborts in named projects.
4. **Explicit confound — why multi-digest sessions show higher cache hit rates (62.4% vs 19.4%).** Naively splitting sessions by `system-prompt-digest` count (`1` vs `>1`) gives a counter-intuitive result (`19.4%` vs `62.4%` per-session mean cache hit). Inspection reveals a textbook **session-length confound**: single-digest sessions are heavily skewed toward short 1–3 turn queries (cold cache, `24.7%` pooled hit in `<10`-turn sessions), whereas multi-digest sessions occur almost exclusively in long multi-hour runs where subsequent turns hit cache (`71.1%` pooled hit in `>=10`-turn sessions). **Observational correlation is therefore NOT treated as causal evidence**; cache prefix stability must be tested with controlled wire-payload checks (`scripts/payload_gate.py`) or alternating trials (`scripts/nof1_power.py`).

## 5. Threats to Validity

- Single-developer longitudinal workload; task mix, underlying models, and upstream runtime versions shifted across the 12-week window.
- `aborted` captures user-initiated cancellations as well as runtime stops; it is an upper bound on involuntary failures.
- Raw traces stay local and gitignored; only aggregate counts and the deterministic analysis script enter version control.
