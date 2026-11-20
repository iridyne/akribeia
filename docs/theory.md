# Theory: model, harness, and what counts as evidence

This document states the theoretical commitments of the repository. It is deliberately short. Each claim has an ID in `claims/literature.toml`; the prose here is the narrative, the ledger is the source of truth.

## 1. The unit of analysis is the harness, not the prompt

A language model alone is not an agent. The agent emerges from a runtime layer that couples four things (LIT-001):

1. a loop that interleaves reasoning, action, and observation;
2. a tool interface that lets the model perceive and alter an environment;
3. context management that decides what enters and leaves the model's window;
4. at least one control mechanism whose effect does not depend on the model choosing to cooperate.

A system that lacks any one of these is a neighboring category: a single-pass generator, an SDK, a naive wrapper, or a demo that trusts the model's word. The definition is binary in membership and gradual in quality. A minimal loop that re-runs a test suite and declares success only when it passes is an embryonic harness; the difference from a mature harness is the robustness of the control layer, not membership.

This matters for research because it gives a stable comparison unit. "Model X scored Y" is underspecified unless the harness is named and versioned (LIT-013).

## 2. Performance is a system function, not a model scalar

The system-scaling framing decomposes long-horizon performance as

$$
\mathcal{P}_H = \Phi(\mathcal{R}, \mathcal{M}, \mathcal{C}, \mathcal{S}, \mathcal{O}, \mathcal{G}),
$$

where `R` is the reasoning substrate, `M` memory quality, `C` context construction, `S` skill routing across tools and subagents, `O` orchestration, and `G` verification and governance (LIT-002). The authors are explicit that this is a conceptual organization, not a closed-form model, and that the factors are not orthogonal.

The practical consequence is a rule for interventions: name the factor you are changing, and hold the others fixed or measure them. A prompt edit that changes both context construction and control is two interventions.

Three bottlenecks recur (LIT-002):

- **Context governance.** The threat is exposure without access: more tokens, not more attention. The move is to treat each turn's context as the output of a selection policy, not a fixed buffer.
- **Trustworthy memory.** The threat is stale-but-confident: a note that was true, ranked highly, and now points at a deleted symbol. Trust must be re-established at retrieval against the live environment.
- **Skill routing and verification.** The threat is confident-but-unchecked: a specialized subagent returns plausible output that no downstream layer validates. Routing and verification are coupled; scaling one without the other produces faster, less reliable progress.

## 3. Scaffolding effects are real but bounded

The strongest empirical anchor is not that scaffolding always wins; it is that scaffolding choices matter and can hurt.

- Agent–computer interface design alone moved SWE-bench accuracy substantially with a fixed backbone (LIT-003).
- In METR's 195-task study, post-training from GPT-4 base to the 0613 release moved success from 5% to 30%, while the authors' additional scaffolding work moved it from 30% to 38%, not statistically significant (LIT-004).
- The same study found that LangChain ReAct and AutoGPT scaffolds performed noticeably worse than the authors' basic scaffold on the same model: it is easy to make an agent worse with plausible-looking prompting and scaffolding (LIT-005).
- A simple three-phase agentless pipeline outperformed complex agents on SWE-bench Lite at lower cost in the original comparison (LIT-006).

The honest reading is conditional: once a model is competently tuned for agency, large gains from hand-built scaffolding are hard to obtain, and the variance of scaffold changes is high. This repository therefore treats every scaffold change as an experiment, not an improvement by default. It also prefers deletion over addition: removing a mechanism is easier to justify than adding one.

## 4. Failures must be localized before they are repaired

Outcome-level labels ("the task failed") cannot choose an intervention. The interaction-centric taxonomy labels a failure by the edge on which it occurred and the side at fault (LIT-007):

```
comp1 — comp2 · fault: side
```

The attribution rule is to trace backward from the observed failure to the earliest failure from which execution did not recover. Later errors are consequences. A tool error that the model ignores and a tool error the wrapper suppresses share the same edge but have different fault sides and different repairs.

The multi-agent taxonomy reaches a compatible conclusion from a different dataset: failures cluster into specification issues, inter-agent misalignment, and task verification, and prompt-level patches often do not fix them (LIT-008).

For this repository, every incident must name:

- the observed system-level failure;
- the earliest unrecoverable event;
- the edge and the fault side;
- the failure mode;
- the intervention that follows, or the reason none does.

## 5. Self-improvement is an update operator on the scaffold

The self-improvement literature formalizes an agent as a foundation model plus an operational scaffold of prompts, memory, tools, and control logic. Self-improvement is a self-induced update operator that commits changes to model parameters or scaffold components, driven by intrinsic demonstrations, evaluative feedback, or exploratory experience (LIT-010).

This repository implements only scaffold updates, and only through a gated loop:

1. an execution signal (a real trace or a metric);
2. a localized failure or a measured gap;
3. a hypothesis;
4. a preregistered intervention and falsifier;
5. evidence;
6. a claim update.

There is no weight updating, no self-modifying code, and no autonomous merge. The long-term version of that question — whether an agent should rewrite its own harness code — is out of scope until the evaluation layer is strong enough to catch regressions.

## 6. Evidence hierarchy

Not all evidence is equal. The repository uses this order, from strongest to weakest:

1. **Replicated local effect** with a preregistered metric, a control period, and no confound that explains the result.
2. **Single local effect** with a preregistered metric and a plausible mechanism.
3. **Published empirical result** within its stated scope and task distribution.
4. **Published conceptual framework** that organizes mechanisms but makes no quantitative claim.
5. **Practitioner heuristic** (including our own prior experience).
6. **Anecdote** from one session.

A claim's status records the highest level actually achieved, not the level we hope for. A single session is an incident, not evidence. A benchmark result is not a production result. A framework is not a finding.

## 7. What the literature does not settle

These are open questions, not claims:

- the optimal point between autonomy and supervision for a task class;
- which context-curation policy maximizes performance per token;
- how to route skills under heterogeneous subagents;
- how to evaluate a harness longitudinally, including memory hygiene and drift;
- whether scaffold gains persist after a model upgrade;
- how much of a reported agent score is model and how much is harness.

Each becomes a local hypothesis with a falsifier, or it stays out of the configuration.

## 8. Human–machine co-construction

The loop is mixed-initiative in Horvitz's sense (LIT-016): the human sets goals, constraints, and the decision to accept a change; the system infers when to act, gathers evidence, and proposes. The repository automates collection, labeling, and drafting. It does not automate acceptance. That boundary is a design decision (D-004), not a temporary limitation.
