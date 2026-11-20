# PCH — Proof-Carrying Harness

**Every knob carries its proof.**

Agent quality is not model quality. It is `model × harness`: the loop, tools, context policy, memory, and control layer around the model. Yet most harnesses ship as folklore — a pile of prompts, flags, and guardrails whose authors cannot say which paper, which experiment, or which incident justified each line.

The name borrows from *proof-carrying code*: an artifact ships with a certificate that a verifier can check. Here the artifact is a harness configuration, and the certificate is an evidence record — a claim, its source, its status, and the experiment that tests it. The proof is not a mathematical proof; it is a warrant that survives review.

PCH is a research loop that makes every harness change traceable:

- every intervention cites a **claim**;
- every claim is labeled **literature-supported**, **local evidence**, **conceptual**, **contested**, or **hypothesis**;
- every hypothesis gets a preregistered experiment and a falsifier;
- every real failure becomes a labeled **incident** and feeds the next round.

The repository is also a live playground. The author's daily agent sessions are the data source. A weekly batch job turns traces into incidents, metrics, and evidence-backed pull requests. Nothing merges itself.

> We do not ship hypotheses as findings.

## The loop

```mermaid
flowchart LR
  A[Real session] --> B[Trace + metrics]
  B --> C[Failure localization]
  C --> D[Claim: supported or hypothesis]
  D --> E[Intervention]
  E --> F[Pre-registered experiment]
  F --> G[Evidence]
  G --> D
  G --> H[Report + PR]
```

## Why this exists

Three findings motivate the design:

1. The harness is a first-class system, not glue. A system is an agent harness when it has a runtime loop, a tool interface, active context management, and at least one control mechanism independent of the model's obedience (Macedo 2026).
2. Harness choices move outcomes with the model held fixed. Agent–computer interface design alone changed SWE-bench accuracy substantially (Yang et al. 2024), and the same model under different scaffolds performs differently (METR 2024).
3. Failure labels that stop at "the task failed" cannot choose a repair. Localizing the earliest unrecoverable failure to an interaction edge and a fault side tells you whether to change the model, the harness, the environment, or the grader (Raj et al. 2026).

What the literature does **not** settle: the optimal autonomy/control point, context-curation policy, routing policy, or how to evaluate a harness longitudinally. Those become hypotheses here, not claims.

The tooling review — evaluation frameworks, research ledgers, N-of-1 designs, prompt optimizers, trace standards — is in `docs/prior-art.md`, with what we adopted and what we rejected.

## Status taxonomy

| Label | Meaning | Merge rule |
|---|---|---|
| `supported` | An empirical result from a cited study, within its stated scope | Merge with citation |
| `local-evidence` | Measured in this playground, with an experiment ID | Merge with experiment ID |
| `conceptual` | A framework or definition from a paper, not an empirical result | Merge only as framing |
| `hypothesis` | Our untested explanation | Merge behind a flag and a running experiment |
| `contested` | Evidence conflicts or the scope is unclear | Do not build on it |
| `refuted` | Tested and rejected | Keep for the record |
| `decision` | An operational constraint, not evidence | Merge, labeled as a decision |

The distinction is enforced by `scripts/audit.py`: a `justified` change must cite a `supported` claim or a decision; a `hypothesis` change must cite an `H-*` claim that names an experiment and a falsifier.

## What is in the box

| Path | Purpose |
|---|---|
| `docs/theory.md` | Model–harness relationship, evidence hierarchy, open questions |
| `docs/method.md` | The loop, schemas, promotion rules, automation, threats to validity |
| `docs/taxonomy.md` | Failure-localization vocabulary used by incidents |
| `docs/playground.md` | Metrics, data sources, privacy rules, baseline |
| `docs/prior-art.md` | Evaluation frameworks, research ledgers, N-of-1 designs, optimizers, trace standards |
| `claims/literature.toml` | External claims with sources and status |
| `claims/hypotheses.toml` | Local hypotheses with falsifiers and experiments |
| `claims/decisions.toml` | Operational constraints |
| `mapping/omp-changes.toml` | Every intervention mapped to claims and evidence |
| `experiments/*.toml` | Preregistered experiments and results |
| `incidents/*.toml` | Real failures, localized and labeled |
| `ledger/belief_updates.jsonl` | Chronological confidence changes, including downgrades |
| `scripts/audit.py` | Schema, reference, coverage, and secret checks |
| `scripts/report.py` | Renders `reports/ledger.md` from the ledgers |
| `scripts/collect.py` | OMP adapter: pulls session metrics inside the agent runtime |
| `prompts/weekly-review.md` | The batch reviewer's brief |
| `scripts/weekly.sh` | Deterministic report + batch review |
| `scripts/install-schedule.sh` | Installs the weekly LaunchAgent on macOS |
| `adapters/omp/` | Prompt assertion probe and metric collector for the OMP runtime |

## Quickstart

```bash
python3 scripts/audit.py --selftest
python3 scripts/audit.py
python3 scripts/report.py --write
```

Both use the Python standard library only. There is no package to install and no database.

To run the weekly loop once:

```bash
./scripts/weekly.sh
```

To install the macOS schedule (Mondays, 09:00):

```bash
./scripts/install-schedule.sh
```

Disable it with `launchctl bootout gui/$UID/com.iridyne.pch`.

## Cadence

| When | What |
|---|---|
| Every session | Use the harness. Nothing is logged by hand. |
| Weekly | `./scripts/weekly.sh`: metrics, incidents, experiment status, at most one proposal, draft PR. |
| Quarterly | Judge calibration against human labels (`EXP-0012`). |
| On a model change | Mark local evidence `contested`; re-run the affected experiments. |

## Design constraints

1. **Deterministic first.** Guardrails that must hold under latency are code, not judges. LLM judges run only in the weekly batch lane.
2. **Deletion before addition.** The cheapest harness change is the one that removes a mechanism. Additive changes need stronger evidence.
3. **Every automated change is a pull request.** No auto-merge, no silent config rewrite.
4. **No secrets, no raw traces.** The repository holds aggregates and labels only. `audit.py` rejects common key, token, private-IP, and home-path patterns.
5. **One variable per experiment.** A change that bundles three mechanisms cannot attribute its effect.
6. **Model-agnostic by default.** Rules are delivered to the main session and subagents unless a claim justifies a narrower target.

## Contributing

We want counterexamples more than agreement. A useful contribution is one of:

- a **claim** with a source and a scope;
- a **reproduction** that contradicts a claim;
- an **incident** with a trace excerpt and a fault localization;
- an **experiment** with a falsifier and a stop rule.

Open an issue using the matching template, or send a PR. Read `CONTRIBUTING.md` first. The CI runs the same audit you run locally.

## References

- Macedo, S. *What makes a harness a harness: necessary and sufficient conditions for an agent harness.* arXiv:2606.10106, 2026.
- Gu, S. *From Model Scaling to System Scaling: Scaling the Harness in Agentic AI.* arXiv:2605.26112, 2026.
- Raj, H. et al. *Model or Harness? An Interaction-Centric Taxonomy for Localizing Agent Failures.* arXiv:2607.28802, 2026.
- Pan, L. et al. *Natural-Language Agent Harnesses.* arXiv:2603.25723, 2026.
- Ren, Z. et al. *Self-Improvements in Modern Agentic Systems: A Survey.* arXiv:2607.13104, 2026.
- *Towards Portable Specification of the Agent Harness.* arXiv:2610.40917, 2026.
- Cemri, M. et al. *Why Do Multi-Agent LLM Systems Fail?* arXiv:2503.13657, 2025.
- Yang, J. et al. *SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering.* arXiv:2405.15793, 2024.
- Xia, C. S. et al. *Agentless: Demystifying LLM-based Software Engineering Agents.* arXiv:2407.01489, 2024.
- METR. *Measuring the impact of post-training enhancements.* 2024.
- Liu, N. F. et al. *Lost in the Middle: How Language Models Use Long Contexts.* TACL, 2024.
- Khattab, O. et al. *DSPy: Compiling Declarative Language Model Calls into Self-Improving Pipelines.* arXiv:2310.03714, 2023.
- Shinn, N. et al. *Reflexion: Language Agents with Verbal Reinforcement Learning.* arXiv:2303.11366, 2023.
- Horvitz, E. *Principles of Mixed-Initiative User Interfaces.* CHI, 1999.

## License

MIT. See `LICENSE`.
