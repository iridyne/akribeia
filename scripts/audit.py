#!/usr/bin/env python3
"""Validate the PCH ledgers: schema, references, coverage, and secret hygiene.

Standard library only. Exit code 1 on any error.

    python3 scripts/audit.py
    python3 scripts/audit.py --selftest
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CLAIMS_DIR = ROOT / "claims"
MAPPING_DIR = ROOT / "mapping"
EXPERIMENTS_DIR = ROOT / "experiments"
INCIDENTS_DIR = ROOT / "incidents"
BELIEFS = ROOT / "ledger" / "belief_updates.jsonl"

LITERATURE_STATUS = {"supported", "contested", "conceptual", "refuted"}
HYPOTHESIS_STATUS = {"hypothesis", "supported", "contested", "refuted"}
DECISION_STATUS = {"supported", "superseded"}
CHANGE_STATUS = {"justified", "hypothesis", "decision", "unmapped"}
EXPERIMENT_STATUS = {"planned", "running", "complete", "stopped"}
EDGES = {
    "model-owner",
    "model-context",
    "model-memory",
    "model-tool",
    "model-subagent",
    "model-local-environment",
    "model-external-environment",
    "model-third-party",
    "model-grader",
    "unknown",
}
FAULTS = {"model", "owner", "harness", "tool", "environment", "third-party", "grader", "unknown"}

SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "API key"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "GitHub token"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key"),
    (re.compile(r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "private IPv4"),
    (re.compile(r"/Users/[A-Za-z0-9._-]+"), "home-directory path"),
]
TEXT_SUFFIXES = {".md", ".toml", ".jsonl", ".py", ".sh", ".yml", ".yaml", ".cff", ".txt"}


def load(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def load_ledgers() -> dict[str, Any]:
    claims: list[dict[str, Any]] = []
    for name in ("literature.toml", "hypotheses.toml", "decisions.toml"):
        for claim in load(CLAIMS_DIR / name).get("claim", []):
            claims.append({**claim, "_file": name})

    changes: list[dict[str, Any]] = []
    for path in sorted(MAPPING_DIR.glob("*.toml")):
        changes.extend(load(path).get("change", []))

    experiments: list[dict[str, Any]] = []
    for path in sorted(EXPERIMENTS_DIR.glob("*.toml")):
        experiments.extend(load(path).get("experiment", []))

    incidents: list[dict[str, Any]] = []
    for path in sorted(INCIDENTS_DIR.glob("*.toml")):
        incidents.extend(load(path).get("incident", []))

    beliefs: list[dict[str, Any]] = []
    if BELIEFS.exists():
        for line_no, line in enumerate(BELIEFS.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                beliefs.append({**json.loads(line), "_line": line_no})
            except json.JSONDecodeError as exc:
                beliefs.append({"_line": line_no, "_error": str(exc)})

    return {
        "claims": claims,
        "changes": changes,
        "experiments": experiments,
        "incidents": incidents,
        "beliefs": beliefs,
    }


def required(errors: list[str], item: dict[str, Any], fields: tuple[str, ...]) -> None:
    for field in fields:
        value = item.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"{item.get('id', '?')}: missing field {field!r}")


def split_refs(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def check_ledgers(ledgers: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    claims = ledgers["claims"]
    changes = ledgers["changes"]
    experiments = ledgers["experiments"]
    incidents = ledgers["incidents"]
    beliefs = ledgers.get("beliefs", [])

    claim_by_id: dict[str, dict[str, Any]] = {}
    for claim in claims:
        cid = str(claim.get("id", ""))
        required(errors, claim, ("id", "statement", "status", "confidence", "source", "scope"))
        if not cid:
            continue
        if cid in claim_by_id:
            errors.append(f"duplicate claim id {cid}")
        claim_by_id[cid] = claim

        if cid.startswith("LIT-"):
            if claim.get("status") not in LITERATURE_STATUS:
                errors.append(f"{cid}: bad literature status {claim.get('status')!r}")
            required(errors, claim, ("url",))
        elif cid.startswith("H-"):
            if claim.get("status") not in HYPOTHESIS_STATUS:
                errors.append(f"{cid}: bad hypothesis status {claim.get('status')!r}")
            required(errors, claim, ("experiment", "metric", "falsifier"))
        elif cid.startswith("D-"):
            if claim.get("status") not in DECISION_STATUS:
                errors.append(f"{cid}: bad decision status {claim.get('status')!r}")
        else:
            errors.append(f"{cid}: unknown claim prefix")

    experiment_by_id: dict[str, dict[str, Any]] = {}
    for experiment in experiments:
        eid = str(experiment.get("id", ""))
        required(
            errors,
            experiment,
            ("id", "title", "status", "hypothesis", "metric", "baseline", "sample", "falsifier", "stop_rule"),
        )
        if not eid.startswith("EXP-"):
            errors.append(f"{eid}: experiment id must start with EXP-")
        if eid in experiment_by_id:
            errors.append(f"duplicate experiment id {eid}")
        experiment_by_id[eid] = experiment
        if experiment.get("status") not in EXPERIMENT_STATUS:
            errors.append(f"{eid}: bad experiment status {experiment.get('status')!r}")
        hypothesis = str(experiment.get("hypothesis", ""))
        if hypothesis and not hypothesis.startswith("H-"):
            errors.append(f"{eid}: hypothesis must reference H-*")
        if hypothesis and hypothesis not in claim_by_id:
            errors.append(f"{eid}: dangling hypothesis {hypothesis}")
        for ref in split_refs(experiment.get("intervention")):
            if ref.startswith("M-") and ref not in {str(c.get("id")) for c in changes}:
                errors.append(f"{eid}: dangling intervention {ref}")

    for claim in claims:
        if str(claim.get("id", "")).startswith("H-"):
            ref = str(claim.get("experiment", ""))
            if ref and ref not in experiment_by_id:
                errors.append(f"{claim['id']}: dangling experiment {ref}")

    change_by_id: dict[str, dict[str, Any]] = {}
    for change in changes:
        mid = str(change.get("id", ""))
        required(errors, change, ("id", "date", "target", "value", "claims", "status"))
        if not mid.startswith("M-"):
            errors.append(f"{mid}: change id must start with M-")
        if mid in change_by_id:
            errors.append(f"duplicate change id {mid}")
        change_by_id[mid] = change
        status = change.get("status")
        if status not in CHANGE_STATUS:
            errors.append(f"{mid}: bad change status {status!r}")
        refs = split_refs(change.get("claims"))
        if not refs:
            errors.append(f"{mid}: no claims")
        resolved = []
        for ref in refs:
            if ref not in claim_by_id:
                errors.append(f"{mid}: dangling claim {ref}")
            else:
                resolved.append(claim_by_id[ref])
        if status == "justified" and not any(c.get("status") == "supported" for c in resolved):
            errors.append(f"{mid}: justified requires a supported claim")
        if status == "hypothesis" and not any(
            str(c.get("id", "")).startswith("H-") and c.get("status") == "hypothesis" for c in resolved
        ):
            errors.append(f"{mid}: hypothesis requires a live H-* claim")
        if status == "decision" and not any(str(c.get("id", "")).startswith("D-") for c in resolved):
            errors.append(f"{mid}: decision requires a D-* claim")
        for ref in split_refs(change.get("evidence")):
            if ref.startswith("EXP-") and ref not in experiment_by_id:
                errors.append(f"{mid}: dangling evidence {ref}")

    for incident in incidents:
        iid = str(incident.get("id", ""))
        required(
            errors,
            incident,
            ("id", "date", "title", "edge", "fault", "mode", "earliest_unrecoverable", "evidence"),
        )
        if not iid.startswith("INC-"):
            errors.append(f"{iid}: incident id must start with INC-")
        if incident.get("edge") not in EDGES:
            errors.append(f"{iid}: bad edge {incident.get('edge')!r}")
        if incident.get("fault") not in FAULTS:
            errors.append(f"{iid}: bad fault {incident.get('fault')!r}")
        for ref in split_refs(incident.get("intervention")):
            if ref.startswith("M-") and ref not in change_by_id:
                errors.append(f"{iid}: dangling intervention {ref}")

    for belief in beliefs:
        line = belief.get("_line", "?")
        if "_error" in belief:
            errors.append(f"belief line {line}: invalid JSON: {belief['_error']}")
            continue
        for field in ("ts", "claim", "from", "to", "evidence"):
            if not str(belief.get(field, "")).strip():
                errors.append(f"belief line {line}: missing {field}")
        claim_ref = str(belief.get("claim", ""))
        if claim_ref and claim_ref not in claim_by_id:
            errors.append(f"belief line {line}: dangling claim {claim_ref}")

    return errors


def scan_secrets() -> list[str]:
    errors: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        if ".git" in path.parts or "data" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern, label in SECRET_PATTERNS:
            match = pattern.search(text)
            if match:
                rel = path.relative_to(ROOT)
                errors.append(f"{rel}: possible {label}: {match.group(0)[:24]!r}")
    return errors


def summary(ledgers: dict[str, Any]) -> str:
    changes = ledgers["changes"]
    statuses: dict[str, int] = {}
    for change in changes:
        status = str(change.get("status", "unknown"))
        statuses[status] = statuses.get(status, 0) + 1
    unmapped = [str(c.get("id")) for c in changes if c.get("status") == "unmapped"]
    mapped = len(changes) - len(unmapped)
    coverage = (mapped / len(changes) * 100) if changes else 100.0
    lines = [
        "Akribeia audit",
        f"  claims: {len(ledgers['claims'])}",
        "  changes: "
        + ", ".join(f"{key} {value}" for key, value in sorted(statuses.items()))
        + f" (mapped {mapped}/{len(changes)}, {coverage:.0f}%)",
        f"  experiments: {len(ledgers['experiments'])}",
        f"  incidents: {len(ledgers['incidents'])}",
        f"  belief updates: {len(ledgers.get('beliefs', []))}",
    ]
    if unmapped:
        lines.append(f"  unmapped debt: {', '.join(unmapped)}")
    return "\n".join(lines)


def selftest() -> int:
    valid = {
        "claims": [
            {
                "id": "D-001",
                "statement": "test",
                "status": "supported",
                "confidence": "high",
                "source": "test",
                "scope": "test",
            },
            {
                "id": "H-001",
                "statement": "test",
                "status": "hypothesis",
                "confidence": "low",
                "source": "local",
                "scope": "test",
                "experiment": "EXP-0001",
                "metric": "test",
                "falsifier": "test",
            },
        ],
        "changes": [
            {
                "id": "M-001",
                "date": "2026-01-01",
                "target": "test",
                "value": "test",
                "claims": ["H-001"],
                "status": "hypothesis",
                "evidence": "EXP-0001",
            }
        ],
        "experiments": [
            {
                "id": "EXP-0001",
                "title": "test",
                "status": "planned",
                "hypothesis": "H-001",
                "intervention": "M-001",
                "metric": "test",
                "baseline": "test",
                "sample": "test",
                "falsifier": "test",
                "stop_rule": "test",
            }
        ],
        "incidents": [],
        "beliefs": [{"ts": "2026-01-01", "claim": "H-001", "from": "a", "to": "b", "evidence": "test"}],
    }
    valid_errors = check_ledgers(valid)
    if valid_errors:
        print("selftest FAIL: valid fixture rejected", file=sys.stderr)
        for error in valid_errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    invalid = {key: value for key, value in valid.items()}
    invalid["changes"] = [dict(valid["changes"][0], claims=["H-999"])]
    if not check_ledgers(invalid):
        print("selftest FAIL: dangling claim accepted", file=sys.stderr)
        return 1

    print("selftest OK")
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()

    ledgers = load_ledgers()
    errors = check_ledgers(ledgers) + scan_secrets()
    print(summary(ledgers))

    if errors:
        print("\nFAIL", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print("\nOK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())