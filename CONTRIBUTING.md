# Contributing

We want counterexamples more than agreement. A useful contribution is a claim with a source, a reproduction that contradicts a claim, a localized incident, or a preregistered experiment.

## The one rule

**No knob without a proof.** A change to the harness must name the claim it serves and the evidence behind that claim. If the evidence is not there, the change is a hypothesis, and it needs a falsifier before it ships.

## Ways to contribute

### Add or contest a claim

1. Add an entry to `claims/literature.toml` or `claims/hypotheses.toml`.
2. Give it a unique ID (`LIT-*`, `H-*`, or `D-*`).
3. Record the source, URL, version or date, and scope. A claim without a scope is not a claim.
4. Set the status honestly: `supported`, `conceptual`, `contested`, `hypothesis`, or `refuted`.

A local hypothesis also needs `experiment`, `metric`, and `falsifier`. A hypothesis without a falsifier is a preference in disguise.

### Report an incident

Use the incident issue template. The key step is finding the earliest unrecoverable event, not the loudest symptom. Label the edge and the fault side. If you cannot choose, say `unknown` and name the missing evidence.

### Preregister an experiment

Use the experiment template. One variable. A metric with a denominator. A baseline that was measured, not remembered. A stop rule. A falsifier. For a reversible change, prefer ABAB or a randomized alternating schedule with a preregistered seed; before/after is the fallback, labeled quasi-experimental.

### Change the harness

1. Add a `[[change]]` entry to `mapping/omp-changes.toml`.
2. Map it to claims and an experiment.
3. Run the checks below.
4. Commit and push to `main`. The audit and the claim mapping are the review.

## Checks

```bash
python3 scripts/audit.py --selftest
python3 scripts/audit.py
python3 scripts/report.py --write
```

If a rule or prompt changed, also run the OMP prompt assertion probe in `adapters/omp/README.md` and paste the result into the commit message.

## Status discipline

- Never move a claim to `supported` without an experiment that clears its falsifier.
- Never delete a refuted claim. The record is the point.
- Never present a hypothesis as a finding in a report or a README.
- A model change invalidates local evidence. Mark it `contested` until the experiment is re-run.

## Privacy

The repository is public. Do not commit:

- API keys, tokens, cookies, or auth headers;
- private IPs, hostnames, or SSH aliases;
- home-directory paths from a specific machine;
- raw prompts, file contents, or transcripts;
- personal data about anyone.

`scripts/audit.py` rejects common patterns. Redaction is a hard gate.

## Review

A change lands when:

- the audit passes;
- every change maps to a claim;
- the experiment design is stated;
- the ledger is regenerated;
- the claim status matches the evidence.

Disagreement is welcome. Bring a source or a reproduction.