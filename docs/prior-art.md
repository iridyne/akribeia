# Prior art: what exists, what we borrowed, what we rejected

The question is not "did we invent this?" It is "are we on a path that prior work already validated?" This review covers five areas: agent evaluation frameworks, research-process ledgers, single-case experimental design, prompt optimization, and trace standards.

## 1. Agent evaluation frameworks

| Source | Pattern worth stealing | Verdict |
|---|---|---|
| **Inspect AI** (UK AISI) | Separate `solver` (agent), `scorer`, and `metric`; keep tasks declarative; provide an oracle solver to test the plumbing; calibrate judges against human labels; normalize outputs before scoring | **Adopt the concepts.** Not a dependency in v1: our eval surface is a single prompt-assertion probe, and a framework would add more moving parts than it removes. |
| **HAL Harness** (Princeton PLI) | Versioned agent interface (`run(input) -> dict`), cost tracking, trace logging, environment isolation, results shareable with encrypted traces | **Adopt cost + trace + versioning.** Reject the leaderboard and cloud execution: we evaluate one harness, not a model leaderboard. |
| **Terminal-Bench / Harbor** | Sandboxed tasks, oracle mode, contribution checks, task review workflow | **Adopt the contribution workflow** (issue templates, PR checks). No benchmark suite: our tasks are the author's real sessions. |
| **Promptfoo** | Deterministic assertions first; model-graded assertions sparingly; one provider for regression, two for comparison; validate config before running | **Adopt the assertion hierarchy.** CI for the live harness stays a shell probe; Promptfoo is a candidate if the eval set grows beyond a handful of checks. |

Takeaway: a credible eval harness separates the agent, the scorer, and the metric, and it proves the plumbing with a known-good and a known-bad case. Our `audit.py` self-test and the prompt-assertion probe are the minimal version of that.

## 2. Research-process ledgers

| Source | Pattern worth stealing | Verdict |
|---|---|---|
| **Research Ledger Lite** | Seven event types: claim, evidence, experiment, decision, failure, belief update, artifact. Every event must be anchored to an observable (commit, path, transcript, timestamp). JSONL canonical log, Markdown narrative, SQLite index. | **Adopt belief updates and anchors.** We keep TOML instead of JSONL+SQLite: the ledger is small, PR-friendly, and `tomllib` is in the standard library. If the event count grows past a few hundred, add a derived JSONL/SQLite index. |
| **ENCORE** | Standard folder structure; Git tracks code, settings, and documentation, never data or results. | **Already adopted.** `data/` is gitignored; raw traces never enter the repository. |
| **GitHub as a lab notebook** | One issue per experiment; comments carry troubleshooting and intermediate results; closing the issue records the conclusion. | **Adopt through issue templates.** The TOML ledger is the machine record; the issue is the discussion record. |
| **ResearchMemoryKit** | Small set of Markdown files for state, decisions, experiments, and evidence; Git-native. | **Confirms the shape.** We use TOML for structured fields and Markdown for narrative. |

Takeaway: the process record must include failed experiments and belief changes, not only wins. A ledger that only records what worked is a marketing artifact.

## 3. Single-case experimental design (N-of-1)

The playground is one person. Between-subject statistics do not apply. The relevant literature is single-case experimental design.

| Source | Pattern worth stealing | Verdict |
|---|---|---|
| **QuantifyMe** | Multi-stage design (baseline + intervention stages), 4–7 days per stage, stability criteria before advancing. | **Adopt the staging idea.** Our weeks are the natural phase length; a phase advances only after the metric is stable. |
| **StudyMe** | Default ABAB schedule with 7-day phases; balanced phase sequences to reduce temporal bias. | **Adopt ABAB for reversible interventions.** A rule fragment can be toggled; a permanent rule cannot, and needs a different design. |
| **nof1kit** | Preregistered randomization seed; balanced schedules under a maximum-run constraint; simulate power under serial dependence; validate the day index against timestamps. | **Adopt the seed, run constraint, and power caveat.** Report that a before/after comparison with autocorrelated daily metrics can flag effects that are not there. |
| **SCRT / scan / SingleCaseES** | Randomization tests and effect sizes for phase designs. | **Defer.** At 20–40 sessions, a simple randomization test or a permutation test is enough; add the package only if the design grows. |

Takeaway: "before vs after" is the weakest design. Use ABAB or a randomized alternating schedule when the intervention can be toggled; otherwise say explicitly that the design is quasi-experimental and cannot attribute causality.

## 4. Prompt and rule optimization

| Source | Pattern worth stealing | Verdict |
|---|---|---|
| **DSPy / GEPA** | Reflective prompt evolution from execution traces; Pareto front over candidates; a validation set; a separate reflection model. | **Defer to phase 2.** Our weekly reviewer can propose one edit; a full evolutionary optimizer needs a stable metric and a held-out set first. GEPA is the leading candidate when the eval set is large enough. |
| **OpenEvolve** | Evolutionary program search with an archive and a fitness function. | **Candidate for rule search**, not for acceptance. The same rule applies: no promotion without held-out evidence. |
| **Promptbreeder / OPRO** | Population-based prompt mutation. | **Not now.** They optimize against a metric; with 20 sessions, the metric is too noisy. |

Takeaway: optimization without a validation set is overfitting with extra steps. The batch lane may propose; the experiment decides.

## 5. Trace and metric standards

| Source | Pattern worth stealing | Verdict |
|---|---|---|
| **OpenTelemetry GenAI semantic conventions** | Standard attribute names for agent spans (`gen_ai.operation.name`, `gen_ai.provider.name`, `gen_ai.agent.name`, `gen_ai.conversation.id`), model, usage, and errors. | **Adopt the naming where the local data maps cleanly.** Do not force a full OTel pipeline into a single-user macOS setup. If we later export traces, use the convention. |
| **HAL cost accounting** | Report cost and tokens alongside success; a Pareto frontier, not a single score. | **Adopt.** Every experiment records tokens and wall-clock cost. |

## 6. What this changed in PCH

The review changed five things:

1. **Experiment design.** Reversible interventions get an ABAB or randomized alternating schedule with a preregistered seed. Before/after is labeled quasi-experimental.
2. **Judge calibration.** The weekly reviewer's labels are calibrated against human labels on a sample. Agreement is reported; an uncalibrated judge cannot promote a claim.
3. **Belief updates.** A chronological `ledger/belief_updates.jsonl` records changes in confidence, including downgrades. Claims are the current state; belief updates are the history.
4. **Oracle checks.** `audit.py --selftest` feeds a known-good and a known-bad ledger through the validator, so a broken validator cannot pass silently.
5. **Tooling restraint.** No MLflow, W&B, LangSmith, or hosted eval platform in v1. They solve multi-user scale and add data movement; the current bottleneck is evidence quality, not storage.

## 7. Links

- Inspect AI — <https://inspect.aisi.org.uk/>
- HAL Harness — <https://github.com/princeton-pli/hal-harness>
- HAL paper — <https://arxiv.org/html/2510.11977>
- Terminal-Bench — <https://github.com/harbor-framework/terminal-bench>
- Promptfoo assertions — <https://www.promptfoo.dev/docs/configuration/expected-outputs/>
- EvalGen / Who Validates the Validators — <https://dl.acm.org/doi/fullHtml/10.1145/3654777.3676450>
- Research Ledger Lite — <https://t46.github.io/blogs/research_ledger_lite.html>
- ENCORE — <https://pmc.ncbi.nlm.nih.gov/articles/PMC11405857/>
- GitHub as a lab notebook — <https://pmc.ncbi.nlm.nih.gov/articles/PMC11844616/>
- QuantifyMe — <https://www.mdpi.com/1424-8220/18/4/1097>
- StudyMe — <https://doi.org/10.1186/s13063-022-06893-7>
- nof1kit — <https://haomeng797-ship-it.github.io/nof1kit/>
- GEPA — <https://github.com/gepa-ai/gepa>
- DSPy GEPA — <https://dspy.ai/current/diving-deeper/gepa-in-depth/>
- OpenEvolve — <https://github.com/algorithmicsuperintelligence/openevolve>
- OpenTelemetry GenAI semantic conventions — <https://github.com/open-telemetry/semantic-conventions-genai>

## 8. Open questions

- Is Inspect AI worth adopting once the eval set exceeds ~20 assertions?
- Does GEPA improve rule quality on a held-out set without overfitting to one user?
- Should the weekly reviewer be a different model from the one being reviewed? (Independence reduces self-preference; cost is acceptable in the batch lane.)
- How many sessions are needed before a local effect is credible under serial dependence? Simulate the design before running the next experiment.
