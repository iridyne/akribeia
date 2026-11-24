#!/usr/bin/env python3
"""Render reports/ledger.md from the TOML ledgers. Standard library only."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from audit import ROOT, load_ledgers

LEDGER = ROOT / "reports" / "ledger.md"


def cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()


def table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(cell(value) for value in row) + " |")
    return "\n".join(lines)


def render() -> str:
    ledgers = load_ledgers()
    claims = sorted(ledgers["claims"], key=lambda item: str(item.get("id")))
    changes = sorted(ledgers["changes"], key=lambda item: str(item.get("id")))
    experiments = sorted(ledgers["experiments"], key=lambda item: str(item.get("id")))
    incidents = sorted(ledgers["incidents"], key=lambda item: str(item.get("id")))

    literature = [c for c in claims if str(c.get("id", "")).startswith("LIT-")]
    hypotheses = [c for c in claims if str(c.get("id", "")).startswith("H-")]
    decisions = [c for c in claims if str(c.get("id", "")).startswith("D-")]

    unmapped = [c for c in changes if c.get("status") == "unmapped"]
    coverage = (len(changes) - len(unmapped)) / len(changes) * 100 if changes else 100.0

    out: list[str] = [
        "# Ledger",
        "",
        "Generated from `claims/`, `mapping/`, `experiments/`, and `incidents/` by `scripts/report.py`.",
        "Do not edit by hand. Run `python3 scripts/report.py --write`.",
        "",
        f"**Coverage:** {len(changes) - len(unmapped)}/{len(changes)} changes mapped to a claim ({coverage:.0f}%).",
        "",
        "## Literature claims",
        "",
        table(
            ["ID", "Status", "Statement", "Source"],
            [[c.get("id"), c.get("status"), c.get("statement"), c.get("source")] for c in literature],
        ),
        "",
        "## Local hypotheses",
        "",
        table(
            ["ID", "Status", "Statement", "Experiment", "Falsifier"],
            [
                [c.get("id"), c.get("status"), c.get("statement"), c.get("experiment"), c.get("falsifier")]
                for c in hypotheses
            ],
        ),
        "",
        "## Decisions",
        "",
        table(
            ["ID", "Statement", "Source"],
            [[c.get("id"), c.get("statement"), c.get("source")] for c in decisions],
        ),
        "",
        "## Changes",
        "",
        table(
            ["ID", "Target", "Status", "Claims", "Evidence"],
            [
                [c.get("id"), c.get("target"), c.get("status"), ", ".join(c.get("claims", [])), c.get("evidence", "")]
                for c in changes
            ],
        ),
        "",
        "## Experiments",
        "",
        table(
            ["ID", "Status", "Hypothesis", "Metric", "Falsifier"],
            [
                [e.get("id"), e.get("status"), e.get("hypothesis"), e.get("metric"), e.get("falsifier")]
                for e in experiments
            ],
        ),
        "",
        "## Incidents",
        "",
        table(
            ["ID", "Edge", "Fault", "Mode", "Intervention"],
            [
                [
                    i.get("id"),
                    i.get("edge"),
                    i.get("fault"),
                    i.get("mode"),
                    ", ".join(i.get("intervention", [])),
                ]
                for i in incidents
            ],
        ),
        "",
    ]
    if unmapped:
        out.extend(["## Unmapped debt", "", ", ".join(str(c.get("id")) for c in unmapped), ""])
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write reports/ledger.md")
    parser.add_argument("--check", action="store_true", help="fail if reports/ledger.md is stale")
    args = parser.parse_args()

    content = render()
    if args.write:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.write_text(content, encoding="utf-8")
        print(f"wrote {LEDGER.relative_to(ROOT)}")
        return 0
    if args.check:
        if not LEDGER.exists():
            print(f"missing {LEDGER.relative_to(ROOT)}; run --write", file=sys.stderr)
            return 1
        if LEDGER.read_text(encoding="utf-8") != content:
            print("reports/ledger.md is stale; run python3 scripts/report.py --write", file=sys.stderr)
            return 1
        print("reports/ledger.md is current")
        return 0
    print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())