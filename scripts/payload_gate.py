#!/usr/bin/env python3
"""Provider-agnostic wire-payload contract gate for Akribeia.

Verifies that the serialized request payload actually sent to an LLM provider
contains every mapped harness rule, preserves prompt-cache prefix stability,
and contains no vacuous negative-only assertions (INC-0006).

Standard library only. Supports:
  - OpenAI Chat Completions / Responses API JSON payloads
  - Anthropic Messages API JSON payloads
  - Generic / OMP serialized provider request JSON payloads

Usage:
    python3 scripts/payload_gate.py --selftest
    python3 scripts/payload_gate.py --contract contracts/example-harness-contract.toml \
        --payload examples/demo-payloads/anthropic_good.json
    python3 scripts/payload_gate.py --contract contracts/example-harness-contract.toml \
        --payload examples/demo-payloads/anthropic_broken_cache_drift.json \
        --baseline-payload examples/demo-payloads/anthropic_good.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

VALID_SCOPES = {"system", "developer", "user", "tools", "any"}
VALID_KINDS = {"must_contain", "must_regex", "must_not_contain", "tool_present", "tool_absent"}


@dataclass(frozen=True)
class NormalizedPayload:
    provider: str
    system_text: str
    developer_text: str
    user_text: str
    tool_names: tuple[str, ...]
    raw_json: str

    @property
    def system_prefix_sha256(self) -> str:
        normalized = "\n".join(line.rstrip() for line in self.system_text.splitlines()).strip()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _flatten_content(content: Any) -> str:
    """Extract plain text from string or structured content blocks."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if isinstance(item.get("text"), str):
                    parts.append(item["text"])
                elif isinstance(item.get("content"), (str, list)):
                    parts.append(_flatten_content(item["content"]))
        return "\n".join(p for p in parts if p)
    if isinstance(content, dict):
        if isinstance(content.get("text"), str):
            return content["text"]
        if "content" in content:
            return _flatten_content(content["content"])
    return ""


def _extract_tool_names(raw: dict[str, Any]) -> list[str]:
    names: list[str] = []
    tools = raw.get("tools")
    if isinstance(tools, list):
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            if isinstance(tool.get("name"), str):
                names.append(tool["name"])
            elif isinstance(tool.get("function"), dict) and isinstance(tool["function"].get("name"), str):
                names.append(tool["function"]["name"])
    return sorted(set(names))


def normalize_payload(raw: dict[str, Any]) -> NormalizedPayload:
    """Normalize OpenAI, Anthropic, or generic/OMP provider payloads."""
    system_parts: list[str] = []
    developer_parts: list[str] = []
    user_parts: list[str] = []

    provider = "generic"
    # Anthropic Messages API: top-level `system` (str or content block list)
    if "system" in raw:
        provider = "anthropic"
        text = _flatten_content(raw.get("system"))
        if text:
            system_parts.append(text)
    # OpenAI Responses API: top-level `instructions` + `input`
    if "instructions" in raw:
        provider = "openai-responses"
        text = _flatten_content(raw.get("instructions"))
        if text:
            system_parts.append(text)

    messages = raw.get("messages")
    if not isinstance(messages, list) and isinstance(raw.get("input"), list):
        messages = raw.get("input")

    if isinstance(messages, list):
        if provider == "generic":
            provider = "openai-chat"
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            role = str(msg.get("role", "")).lower()
            text = _flatten_content(msg.get("content"))
            if not text:
                continue
            if role == "system":
                system_parts.append(text)
            elif role == "developer":
                developer_parts.append(text)
            elif role == "user":
                user_parts.append(text)

    return NormalizedPayload(
        provider=provider,
        system_text="\n\n".join(system_parts),
        developer_text="\n\n".join(developer_parts),
        user_text="\n\n".join(user_parts),
        tool_names=tuple(_extract_tool_names(raw)),
        raw_json=json.dumps(raw, ensure_ascii=False, sort_keys=True),
    )


def validate_contract_schema(contract: dict[str, Any]) -> list[str]:
    """Validate contract structure and enforce anti-vacuous assertion guard (INC-0006)."""
    errors: list[str] = []
    assertions = contract.get("assertion", [])
    if not isinstance(assertions, list) or not assertions:
        return ["contract must define at least one [[assertion]] entry"]

    seen_ids: dict[str, dict[str, Any]] = {}
    for idx, item in enumerate(assertions):
        if not isinstance(item, dict):
            errors.append(f"assertion[{idx}]: must be a table")
            continue
        aid = str(item.get("id", "")).strip()
        kind = str(item.get("kind", "")).strip()
        scope = str(item.get("scope", "any")).strip()
        pattern = item.get("pattern")
        if not aid:
            errors.append(f"assertion[{idx}]: missing 'id'")
            continue
        if aid in seen_ids:
            errors.append(f"{aid}: duplicate assertion id")
        seen_ids[aid] = item
        if kind not in VALID_KINDS:
            errors.append(f"{aid}: invalid kind {kind!r} (expected one of {sorted(VALID_KINDS)})")
        if scope not in VALID_SCOPES:
            errors.append(f"{aid}: invalid scope {scope!r} (expected one of {sorted(VALID_SCOPES)})")
        if not isinstance(pattern, str) or not pattern:
            errors.append(f"{aid}: 'pattern' must be a non-empty string")
        if kind == "must_regex" and isinstance(pattern, str):
            try:
                re.compile(pattern)
            except re.error as exc:
                errors.append(f"{aid}: invalid regex {pattern!r}: {exc}")

    # Anti-vacuous guard (INC-0006):
    # A negative assertion (`must_not_contain` or `tool_absent`) can pass vacuously
    # when the extension/component responsible for emitting or rewriting text failed
    # to load. Require an explicit positive `requires_witness` assertion ID.
    for aid, item in seen_ids.items():
        kind = str(item.get("kind", ""))
        if kind in {"must_not_contain", "tool_absent"}:
            witness = str(item.get("requires_witness", "")).strip()
            if not witness:
                errors.append(
                    f"{aid}: negative assertion ({kind}) missing 'requires_witness' "
                    "(anti-vacuous guard, INC-0006)"
                )
            elif witness not in seen_ids:
                errors.append(f"{aid}: requires_witness {witness!r} does not exist")
            elif seen_ids[witness].get("kind") not in {"must_contain", "must_regex", "tool_present"}:
                errors.append(
                    f"{aid}: requires_witness {witness!r} must be a positive assertion "
                    "(must_contain / must_regex / tool_present)"
                )
    return errors


def _scope_text(payload: NormalizedPayload, scope: str) -> str:
    if scope == "system":
        return payload.system_text
    if scope == "developer":
        return payload.developer_text
    if scope == "user":
        return payload.user_text
    if scope == "tools":
        return "\n".join(payload.tool_names)
    return payload.raw_json


def evaluate_contract(
    contract: dict[str, Any],
    payload: NormalizedPayload,
    *,
    baseline_sha256: str | None = None,
    log_text: str | None = None,
) -> dict[str, Any]:
    """Run all contract checks fail-closed and return a structured report."""
    schema_errors = validate_contract_schema(contract)
    if schema_errors:
        return {
            "ok": False,
            "stage": "contract_schema",
            "schema_errors": schema_errors,
            "provider": payload.provider,
            "system_prefix_sha256": payload.system_prefix_sha256,
            "results": [],
            "log_failures": [],
            "cache_check": None,
        }

    # 1. Startup / extension log gate (INC-0005)
    log_failures: list[str] = []
    log_cfg = contract.get("log_gate", {})
    fatal_patterns = log_cfg.get("fatal_patterns", ["Failed to load extension"])
    if log_text is not None:
        for pat in fatal_patterns:
            if re.search(pat, log_text):
                log_failures.append(f"startup log matched fatal pattern: {pat!r}")

    # 2. Evaluate positive assertions first, then negative assertions gated by witness
    assertions = contract["assertion"]
    outcome_by_id: dict[str, bool] = {}
    results: list[dict[str, Any]] = []

    def eval_one(item: dict[str, Any]) -> dict[str, Any]:
        aid = item["id"]
        kind = item["kind"]
        scope = item.get("scope", "any")
        pattern = item["pattern"]
        haystack = _scope_text(payload, scope)

        if kind == "must_contain":
            passed = pattern in haystack
            detail = "found" if passed else f"missing literal {pattern!r} in scope={scope}"
        elif kind == "must_regex":
            passed = re.search(pattern, haystack) is not None
            detail = "matched" if passed else f"regex {pattern!r} did not match scope={scope}"
        elif kind == "tool_present":
            passed = pattern in payload.tool_names
            detail = "present" if passed else f"tool {pattern!r} absent from tool surface"
        elif kind in {"must_not_contain", "tool_absent"}:
            witness_id = item["requires_witness"]
            witness_ok = outcome_by_id.get(witness_id, False)
            if not witness_ok:
                passed = False
                detail = (
                    f"blocked vacuous pass: witness {witness_id!r} failed "
                    "(INC-0006 anti-vacuous guard)"
                )
            elif kind == "must_not_contain":
                passed = pattern not in haystack
                detail = "absent (witness verified)" if passed else f"forbidden {pattern!r} found in scope={scope}"
            else:
                passed = pattern not in payload.tool_names
                detail = "tool absent (witness verified)" if passed else f"forbidden tool {pattern!r} present"
        else:
            passed = False
            detail = f"unsupported kind {kind!r}"

        outcome_by_id[aid] = passed
        return {
            "id": aid,
            "kind": kind,
            "scope": scope,
            "passed": passed,
            "detail": detail,
            "claim": item.get("claim", ""),
        }

    positives = [a for a in assertions if a["kind"] in {"must_contain", "must_regex", "tool_present"}]
    negatives = [a for a in assertions if a["kind"] in {"must_not_contain", "tool_absent"}]
    for item in positives + negatives:
        results.append(eval_one(item))

    # 3. Prompt-cache prefix-hash stability check
    cache_check: dict[str, Any] | None = None
    expected_sha = baseline_sha256 or str(contract.get("cache_gate", {}).get("expected_system_sha256", "")).strip()
    if expected_sha:
        actual_sha = payload.system_prefix_sha256
        matched = actual_sha == expected_sha
        cache_check = {
            "expected_sha256": expected_sha,
            "actual_sha256": actual_sha,
            "stable": matched,
        }

    all_assertions_ok = all(r["passed"] for r in results)
    cache_ok = True if cache_check is None else bool(cache_check["stable"])
    ok = all_assertions_ok and cache_ok and not log_failures

    return {
        "ok": ok,
        "stage": "complete",
        "schema_errors": [],
        "provider": payload.provider,
        "system_prefix_sha256": payload.system_prefix_sha256,
        "passed_count": sum(1 for r in results if r["passed"]),
        "total_count": len(results),
        "results": results,
        "log_failures": log_failures,
        "cache_check": cache_check,
    }


def selftest() -> int:
    """Oracle verification: valid pass, missing rule fail, cache drift fail, vacuous-contract reject."""
    contract_valid = {
        "log_gate": {"fatal_patterns": ["Failed to load extension"]},
        "assertion": [
            {
                "id": "rule-closure",
                "kind": "must_contain",
                "scope": "system",
                "pattern": "Never end a turn on raw tool output.",
                "claim": "H-001",
            },
            {
                "id": "tool-read",
                "kind": "tool_present",
                "scope": "tools",
                "pattern": "read",
                "claim": "D-002",
            },
            {
                "id": "no-legacy-placeholder",
                "kind": "must_not_contain",
                "scope": "any",
                "pattern": "DEPRECATED_LEGACY_PROMPT",
                "requires_witness": "rule-closure",
                "claim": "H-012",
            },
        ],
    }

    good_anthropic = normalize_payload(
        {
            "model": "example-model",
            "system": [{"type": "text", "text": "You are a coding agent. Never end a turn on raw tool output."}],
            "messages": [{"role": "user", "content": "ping"}],
            "tools": [{"name": "read", "input_schema": {"type": "object"}}],
        }
    )
    r1 = evaluate_contract(contract_valid, good_anthropic, baseline_sha256=good_anthropic.system_prefix_sha256)
    if not r1["ok"]:
        print(f"selftest FAIL: valid Anthropic payload rejected: {r1}", file=sys.stderr)
        return 1

    # Broken payload where rule-closure is missing -> must fail BOTH rule-closure AND no-legacy-placeholder
    dead_extension_payload = normalize_payload(
        {
            "model": "example-model",
            "system": [{"type": "text", "text": "You are a coding agent."}],
            "messages": [{"role": "user", "content": "ping"}],
            "tools": [{"name": "read"}],
        }
    )
    r2 = evaluate_contract(contract_valid, dead_extension_payload)
    neg_res = {r["id"]: r["passed"] for r in r2["results"]}
    if r2["ok"] or neg_res["rule-closure"] or neg_res["no-legacy-placeholder"]:
        print(f"selftest FAIL: anti-vacuous witness gate failed to block vacuous pass: {r2}", file=sys.stderr)
        return 1

    # Cache drift check
    drifted = normalize_payload(
        {
            "model": "example-model",
            "system": [{"type": "text", "text": "Timestamp: 2026-11-24. Never end a turn on raw tool output."}],
            "messages": [{"role": "user", "content": "ping"}],
            "tools": [{"name": "read"}],
        }
    )
    r3 = evaluate_contract(contract_valid, drifted, baseline_sha256=good_anthropic.system_prefix_sha256)
    if r3["ok"] or r3["cache_check"]["stable"]:
        print(f"selftest FAIL: system prefix cache drift was not detected: {r3}", file=sys.stderr)
        return 1

    # Schema-level rejection of vacuous negative-only contract (no requires_witness)
    bad_contract = {
        "assertion": [
            {
                "id": "vacuous-neg",
                "kind": "must_not_contain",
                "scope": "any",
                "pattern": "omp-config/system-prompt-replace",
            }
        ]
    }
    r4 = evaluate_contract(bad_contract, dead_extension_payload)
    if r4["ok"] or r4["stage"] != "contract_schema":
        print(f"selftest FAIL: vacuous negative-only contract was accepted: {r4}", file=sys.stderr)
        return 1

    # Startup log fail-closed check (INC-0005)
    r5 = evaluate_contract(contract_valid, good_anthropic, log_text="ERROR: Failed to load extension foo")
    if r5["ok"] or not r5["log_failures"]:
        print(f"selftest FAIL: fatal extension load log did not fail gate: {r5}", file=sys.stderr)
        return 1

    print("payload_gate selftest OK (5/5 oracle checks passed)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true", help="run oracle self-tests")
    parser.add_argument("--contract", type=Path, help="path to TOML assertion contract")
    parser.add_argument("--payload", type=Path, help="path to captured JSON wire payload")
    parser.add_argument("--baseline-payload", type=Path, help="optional baseline JSON payload for cache-prefix check")
    parser.add_argument("--baseline-sha256", type=str, default=None, help="optional expected system prefix sha256")
    parser.add_argument("--log-file", type=Path, help="optional startup log file to scan fail-closed")
    parser.add_argument("--json", action="store_true", dest="as_json", help="emit JSON report")
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    if not args.contract or not args.payload:
        parser.error("--contract and --payload are required unless --selftest is set")

    with args.contract.open("rb") as handle:
        contract = tomllib.load(handle)
    raw_payload = json.loads(args.payload.read_text(encoding="utf-8"))
    payload = normalize_payload(raw_payload)

    baseline_sha = args.baseline_sha256
    if args.baseline_payload:
        base_raw = json.loads(args.baseline_payload.read_text(encoding="utf-8"))
        baseline_sha = normalize_payload(base_raw).system_prefix_sha256

    log_text = args.log_file.read_text(encoding="utf-8", errors="ignore") if args.log_file else None
    report = evaluate_contract(contract, payload, baseline_sha256=baseline_sha, log_text=log_text)

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        status = "PASS" if report["ok"] else "FAIL"
        print(
            f"Akribeia payload gate: {status} "
            f"(provider={report['provider']}, system_sha256={report['system_prefix_sha256'][:12]})"
        )
        for err in report["schema_errors"]:
            print(f"  SCHEMA ERROR: {err}")
        for err in report["log_failures"]:
            print(f"  LOG ERROR: {err}")
        for r in report["results"]:
            mark = "OK" if r["passed"] else "FAIL"
            print(f"  [{mark}] {r['id']} ({r['kind']}/{r['scope']}): {r['detail']}")
        if report["cache_check"] is not None:
            cc = report["cache_check"]
            mark = "OK" if cc["stable"] else "DRIFT"
            print(
                f"  [{mark}] prompt-cache prefix: actual={cc['actual_sha256'][:12]} "
                f"expected={cc['expected_sha256'][:12]}"
            )

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
