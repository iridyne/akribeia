# Taxonomy: localizing a failure before repairing it

We adopt the interaction-centric taxonomy (LIT-007) because it answers the only question that matters for a repair: **which component should change?**

A label has three parts:

```
edge · fault: side · mode
```

- **Edge** — the interaction where the earliest unrecoverable failure happened.
- **Fault side** — the component responsible: `model`, `owner`, `harness`, `tool`, `environment`, `third-party`, or `grader`.
- **Mode** — the failure pattern within that edge.

## Attribution rule

1. Start from the observed system-level failure.
2. Walk backward to the earliest event from which execution did not recover.
3. Label that event, not its downstream symptoms.
4. If the evidence is insufficient to choose, record `unknown` and the missing evidence. Do not guess.

## Edges used in this playground

| Edge | Typical modes | What a repair looks like |
|---|---|---|
| `model–owner` | premature termination / satisficing, instruction-following failure, over-initiative, under-initiative | rule, prompt, or acceptance gate; sometimes a scope clarification |
| `model–context` | goal drift, state-tracking failure, context-rationale erosion | context policy, compaction rule, reminder placement |
| `model–memory` | missed read/write, staleness, pollution, over-generalization | retrieval policy, verification against the live environment |
| `model–tool` | incorrect tool selection, malformed arguments, feedback neglect, recovery failure, mistranslation | tool interface, sanctioned alternative path, deterministic gate |
| `model–subagent` | delegation failure, communication failure | brief schema, context handoff, output contract |
| `model–local environment` | observation failure, recovery failure | better observation, smaller step, retry policy |

## Modes that matter here

### Satisficing / premature termination (`model–owner`)

The agent stops when the output looks finished, not when the task is finished. A raw tool result presented as the answer is the canonical case. The repair is an explicit closure contract plus a metric, not a longer prompt.

### Instruction-following failure (`model–owner`)

The instruction is present and understood but not followed. Distinguish this from context-rationale erosion: if compaction removed the instruction, the harness is at fault; if the instruction is still in context, the model is.

### Incorrect tool selection (`model–tool`)

The model uses a tool that violates the routing policy. Before assigning fault to the model, check whether the harness offered a legitimate path for the task. A prohibition without an alternative is a harness gap.

### Tool feedback neglect (`model–tool`)

The tool returned the error; the model ignored it. This is model-side. A deterministic gate can still catch the downstream action.

### Tool recovery failure (`model–tool`)

The call failed and the model did not retry, diagnose, or route around it. Check whether the error text named the next action. If not, the tool interface shares fault.

### Context-rationale erosion (`model–context`)

Compaction removed a constraint needed later. If the harness decided the compaction, the fault is harness-side; if the model requested it, model-side. Record which.

### Delegation failure (`model–subagent`)

The orchestrator assigns scope or dependencies incorrectly, or the subagent omits a constraint. The brief is the artifact to repair.

## Worked example: the same symptom, two faults

An agent reports that a tool call succeeded when it failed.

- If the wrapper suppressed the error, the label is `tool–model · fault: tool`. Repair the wrapper.
- If the wrapper returned the error and the model ignored it, the label is `tool–model · fault: model`. Repair the rule or add a gate.

The symptom is identical. The intervention is not. This is why outcome-level labels are insufficient.

## Relation to multi-agent taxonomies

The multi-agent taxonomy (LIT-008) groups failures into specification, inter-agent misalignment, and task verification. Those categories are compatible with the edge model: specification issues usually land on `model–owner` or `model–grader`; misalignment on `model–subagent`; verification on `model–grader` or the harness's verifier. We use the interaction taxonomy for local incidents because it names the repair target directly.
