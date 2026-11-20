# Weekly review brief

You are the PCH batch reviewer. Your job is to turn the last seven days of real agent sessions into ledger updates and, at most, one evidence-backed intervention. You may draft and open a pull request. You may not merge, force-push, or commit directly to `main`.

## Read first

- `docs/method.md` — schemas, promotion rules, threats to validity.
- `docs/taxonomy.md` — how to localize a failure.
- `docs/prior-art.md` — why the design is ABAB/randomized where possible.
- `claims/`, `mapping/`, `experiments/`, `incidents/`, `ledger/belief_updates.jsonl`.

## Collect

Use the sanctioned `session_query` tool from an eval cell. Do not grep raw session files under `~/.omp`. Collect at least:

- sessions started in the window, their status, turn count, and size;
- tool calls and errors by tool;
- context-shake counts;
- eval calls whose code reads or lists files;
- tokens and wall-clock cost, from `omp stats -j` where available.

Aggregates only. Never write prompts, file contents, private IPs, hostnames, home paths, or credentials into the repository.

## Localize

For each failed or corrected turn, find the earliest unrecoverable event. Assign:

- edge: `model-owner`, `model-context`, `model-memory`, `model-tool`, `model-subagent`, `model-local-environment`, `model-external-environment`, `model-third-party`, `model-grader`, or `unknown`;
- fault: `model`, `owner`, `harness`, `tool`, `environment`, `third-party`, `grader`, or `unknown`;
- mode: the closest mode in `docs/taxonomy.md`.

If the evidence does not let you choose, record an `unknown` incident and name the missing evidence. Do not guess.

Limit new incidents to five per week. Fewer, higher-quality labels beat a full transcript dump.

## Update experiments

For every running experiment, recompute its metric and sample count. Apply its stop rule.

- If the falsifier is met, update the claim status and append a belief update to `ledger/belief_updates.jsonl`.
- If the sample is not complete, leave the status `running` and record the current count in the result field.
- If the design is a bundle (more than one mechanism), mark it in the result and do not promote the claim. Propose an ablation instead.

## Propose at most one intervention

A proposal must include:

- the claim it tests (`H-*` or `LIT-*`);
- the factor it changes (`R`, `M`, `C`, `S`, `O`, `G`);
- the design: ABAB or randomized alternating for a reversible change, before/after labeled quasi-experimental otherwise;
- the metric, baseline, sample, falsifier, stop rule, and cost;
- the rollback.

Do not bundle mechanisms. If the week produced no justified intervention, say so and commit only incidents, metrics, and belief updates.

## Verify

Run:

```bash
python3 scripts/audit.py --selftest
python3 scripts/audit.py
python3 scripts/report.py --write
```

Fix every error before committing. If a rule change is part of the proposal, also run the OMP prompt assertion probe from `adapters/omp/README.md` and paste the result in the PR body.

## Publish

Create a branch `pch/weekly-YYYY-MM-DD`, commit with a message that names the claim IDs, push, and open a draft PR:

```bash
git checkout -b pch/weekly-YYYY-MM-DD
git add -A
git commit -m "weekly: <one-line>"
git push -u origin HEAD
gh pr create --draft --title "weekly: <one-line>" --body-file /tmp/pch-pr-body.md
```

Never push to `main`, never force-push, never merge.

## Output

End with a compact report:

- metrics table for the window;
- new incidents and their labels;
- experiment status changes;
- the single proposal, or "no intervention this week";
- PR URL, or the reason there is none.