# Method: the evidence-gated harness loop

## 1. Artifacts

| Artifact | Schema | Owner | Changes when |
|---|---|---|---|
| Claim | `claims/*.toml` | anyone | a source is added, a status changes, an experiment concludes |
| Change | `mapping/omp-changes.toml` | whoever changes the harness | an intervention is applied or reverted |
| Experiment | `experiments/*.toml` | whoever proposes the intervention | preregistration, status change, result |
| Incident | `incidents/*.toml` | whoever observes the failure | a real failure is localized |
| Belief update | `ledger/belief_updates.jsonl` | whoever changes a belief | a confidence or status changes, including downgrades |
| Report | `reports/ledger.md` | `scripts/report.py` | generated, never hand-edited |

The ledgers are the source of truth. Prose documents explain them; they do not override them.

## 2. The weekly loop

1. **Collect.** Pull the last seven days of sessions, tool calls, errors, policy hits, and context-shake counts. Aggregate only.
2. **Localize.** For each failed or corrected turn, find the earliest unrecoverable event, assign an edge and a fault side, and label the mode. If the evidence is insufficient, record an `unknown` incident rather than guessing.
3. **Compare.** Recompute the metrics of every running experiment. Apply its stop rule. A running experiment that has met its sample and missed its falsifier is marked `refuted`.
4. **Propose.** At most one new intervention per week. It must name the factor it changes, the claim it tests, the metric, the baseline, the sample, and the falsifier. Choose the design before running it: ABAB or a randomized alternating schedule for a reversible change, before/after only as a labeled quasi-experiment.
5. **Verify.** Run `scripts/audit.py`, regenerate the ledger, and run the narrowest check that exercises the change.
6. **Publish.** Open a pull request. Never merge automatically.

The weekly batch is the only place an LLM judge is allowed (D-002). Interactive guardrails stay deterministic.

## 3. Claim schema

```toml
[[claim]]
id = "LIT-001"                  # LIT-*, H-*, D-*
statement = "..."
status = "supported"            # supported | contested | conceptual | hypothesis | refuted
confidence = "high"             # high | medium | low
source = "Macedo 2026"
url = "https://arxiv.org/abs/2606.10106"
scope = "definition"            # task distribution / setting where it holds
notes = "..."
```

A local hypothesis adds:

```toml
experiment = "EXP-0001"
metric = "..."
falsifier = "..."
```

Promotion rule:

- `hypothesis → supported` requires the experiment's sample, a preregistered metric, and a result that clears the falsifier.
- A label produced by an LLM reviewer counts only after calibration against human labels on a sample of at least 20 incidents, with the agreement statistic reported (Cohen's kappa for categorical labels). An uncalibrated judge may draft, not promote.
- `hypothesis → refuted` requires the same evidence in the opposite direction.
- A single session never promotes a hypothesis. It can create an incident and a hypothesis.
- A model upgrade invalidates local evidence unless the experiment is re-run. Mark it `contested` until then.

## 4. Change schema

```toml
[[change]]
id = "M-001"
date = "2026-11-20"
target = "RULES.md:17"
value = "..."
claims = ["H-002", "LIT-007"]
status = "hypothesis"           # justified | hypothesis | decision | unmapped
evidence = "EXP-0002"
notes = "..."
```

Audit rules:

- `justified` must cite at least one `supported` claim.
- `hypothesis` must cite at least one `H-*` claim with an experiment and a falsifier.
- `decision` must cite at least one `D-*` claim.
- `unmapped` is allowed only for a recorded change with no justification yet; it is a debt marker, not a resting state. The audit reports the count.

## 5. Experiment schema

```toml
[[experiment]]
id = "EXP-0001"
title = "..."
status = "running"              # planned | running | complete | stopped
hypothesis = "H-001"
intervention = "M-002, M-003"
metric = "..."
baseline = "..."
sample = "20 sessions"
falsifier = "..."
stop_rule = "..."
started = "2026-11-20"
result = ""
```

One variable per experiment. If an intervention bundles mechanisms, split it or mark the experiment `exploratory` and do not promote its claim.

Design field:

```toml
design = "ABAB; 7-day phases; seeded schedule; primary metric ..."
power = "20 sessions per phase; serial dependence reduces effective n"
```

Reversible interventions (a rule fragment that can be toggled) use ABAB or a randomized alternating schedule with a preregistered seed and a maximum run length. Irreversible interventions (a rule that must stay on) use a before/after design and are labeled quasi-experimental. Report the limitation; do not launder it as a causal effect.

## 6. Incident schema

```toml
[[incident]]
id = "INC-0001"
date = "2026-11-20"
title = "..."
edge = "model-owner"
fault = "model"                 # model | owner | harness | tool | environment | third-party | grader
mode = "satisficing"
earliest_unrecoverable = "..."
intervention = ["M-002"]
evidence = "..."
```

The `mode` vocabulary is in `docs/taxonomy.md`. The `edge` is the interaction, not the symptom's location.

## 7. Automation

```
session store ──► collect.py (deterministic) ──► data/*.json (local, gitignored)
                                                   │
weekly.sh ──► report.py (deterministic) ───────────┤
      └────► omp -p weekly-review.md (batch LLM) ──┴──► ledgers + report + PR
```

- `collect.py` runs inside the agent runtime and uses the session query API. It never reads raw session files.
- `audit.py --selftest` runs a known-good and a known-bad ledger through the validator, so a broken validator cannot pass silently. This is the oracle check borrowed from evaluation harnesses.
- Costs and tokens are recorded next to every experiment result; a change that improves a metric at a much higher token cost is not automatically an improvement.
- `weekly.sh` is the only scheduled entry point. It writes a log under `data/`.
- The batch reviewer may edit `claims/`, `experiments/`, `incidents/`, and `mapping/`. It may open a PR. It may not merge, force-push, or edit `main` directly.
- CI runs `audit.py` and `report.py --check` on every push and PR.

## 8. Threats to validity

- **Confounding by model drift.** The provider can change a model behind an alias. Record the model ID and date; re-run experiments after a suspected change.
- **Selection bias.** Failed sessions are more likely to be inspected. Compare against the full denominator, not only the incidents.
- **LLM judge bias.** The weekly reviewer may prefer changes that look like its own style. Require a deterministic metric for any promotion; use the judge only for labeling and drafting.
- **Overfitting to one user.** A local effect is local. State the scope; do not present it as a general finding.
- **Goodharting the metric.** Optimizing "premature endings" can produce verbose turns that end with a conclusion but add no information. Pair every efficiency metric with a quality metric.
- **Survivorship in the ledger.** Refuted claims stay in the repository. Deleting them would make the record look cleaner than the evidence.
- **Serial dependence.** Daily metrics are autocorrelated. A before/after split can flag an effect that is not there; prefer an alternating design and a randomization test. See `docs/prior-art.md` for the N-of-1 prior art.
- **Judge self-preference.** The weekly reviewer may favor its own edits. Use a different model for review where possible, and require a deterministic metric for promotion.

## 9. Promotion and rollback

A change is promoted when its experiment clears the falsifier and the audit passes. A change is rolled back when:

- a running experiment shows a regression on its guardrail metric;
- the change cannot be mapped to a claim after one review cycle;
- the change increases tool-error rate or policy-hit rate without a compensating gain.

Rollback is a normal outcome, recorded as an incident or an experiment result, not hidden.
