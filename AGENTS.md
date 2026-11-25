# Repository rules for agents

This repository is an evidence ledger, not a chat log. Before editing:

1. Read `docs/method.md`, `docs/taxonomy.md`, and `docs/prior-art.md`.
2. Every change needs a claim. If you cannot name one, add the change as `unmapped` debt and say so.
3. Never invent a citation, a version number, a benchmark score, or a DOI. If you did not read the source, it is a hypothesis.
4. Do not promote a claim to `supported` from a single session or an uncalibrated judge.
5. One variable per experiment. Bundles are exploratory and cannot promote a claim.
6. Run `python3 scripts/audit.py --selftest`, `python3 scripts/audit.py`, and `python3 scripts/report.py --write` before you finish.
7. Inspect files with `read`, `grep`, and `glob`. Do not use shell `cat`/`grep`/`sed` for file inspection.
8. Never commit secrets, raw prompts, private hosts, or home paths.
9. This repository has a single maintainer: commit and push directly to `main`. Force-push is still forbidden. No PR is required.
10. If a rule change is part of the work, run the OMP prompt assertion probe and paste the output.

The goal is not a clean story. The goal is a record that survives a hostile reviewer.