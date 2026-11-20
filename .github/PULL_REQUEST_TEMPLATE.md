# Pull request

## What this changes

<!-- One paragraph. Name the claim IDs and change IDs. -->

## Evidence

- Claim(s):
- Experiment:
- Result / expected result:
- Falsifier:

## Status

- [ ] `justified` — cites a `supported` claim
- [ ] `hypothesis` — cites a live `H-*` claim with an experiment and a falsifier
- [ ] `decision` — cites a `D-*` claim
- [ ] `unmapped` — debt; explain why it cannot wait for a claim

## Verification

- [ ] `python3 scripts/audit.py --selftest`
- [ ] `python3 scripts/audit.py`
- [ ] `python3 scripts/report.py --write` and committed the ledger
- [ ] OMP prompt assertion probe, if a rule changed
- [ ] No secrets, raw prompts, private hosts, or home paths

## Rollback

<!-- How to undo this in one step. -->

## Risks

<!-- Confounds, cost, and what would make you revert. -->