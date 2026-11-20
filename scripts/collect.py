"""OMP adapter for PCH.

Run inside an OMP eval kernel:

    %load ~/Projects/proof-carrying-harness/scripts/collect.py

It uses the sanctioned session_query tool, writes data/metrics-<date>.json,
and prints a summary. It never reads raw session files.

The two trace-level metrics (premature_endings_per_100 and
eval_file_reads_per_100) need turn-level labels; the weekly reviewer
computes them. This collector provides denominators and deterministic
tool metrics.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

PCH_HOME = Path(os.environ.get("PCH_HOME", Path.home() / "Projects" / "proof-carrying-harness"))
WINDOW_DAYS = int(os.environ.get("PCH_WINDOW_DAYS", "30"))
MAX_SIDS_PER_QUERY = 50


async def _details(payload: dict[str, Any]) -> dict[str, Any]:
    result = await tool.session_query(payload)
    if isinstance(result, dict):
        details = result.get("details", result)
    else:
        details = getattr(result, "details", result)
    if isinstance(details, dict):
        return details
    return getattr(details, "__dict__", {})


def _rows(details: dict[str, Any]) -> list[dict[str, Any]]:
    rows = details.get("rows", [])
    return rows if isinstance(rows, list) else []


def _chunks(items: list[str], size: int = MAX_SIDS_PER_QUERY) -> list[list[str]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


async def _sql_rows(sids: list[str], query: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for chunk in _chunks(sids):
        rows.extend(_rows(await _details({"action": "sql", "from": {"sids": chunk}, "query": query})))
    return rows


def _day(value: Any) -> str:
    if isinstance(value, str):
        return value[:10]
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000 if value > 10**12 else value).date().isoformat()
    return ""


def _ratio(part: int, whole: int) -> float:
    return round(part / whole, 4) if whole else 0.0


async def collect() -> dict[str, Any]:
    cutoff = (date.today() - timedelta(days=WINDOW_DAYS)).isoformat()
    sessions = _rows(await _details({"action": "sessions", "limit": 1000}))
    recent = [row for row in sessions if _day(row.get("created")) >= cutoff]
    sids = [row.get("sid") for row in recent if row.get("sid")]

    private_tmp = sum(1 for row in recent if row.get("project") == "--private-tmp--")
    statuses: dict[str, int] = {}
    for row in recent:
        key = str(row.get("status", "unknown"))
        statuses[key] = statuses.get(key, 0) + 1
    turns = sorted(int(row.get("assistantTurns") or 0) for row in recent)
    median_turns = turns[len(turns) // 2] if turns else 0

    tools: list[dict[str, Any]] = []
    shake: dict[str, Any] = {"shaken": None, "entries": None, "ratio": None}
    eval_reads: dict[str, Any] = {
        "calls": None,
        "source": "trace labels by the weekly reviewer",
        "note": "src.events.text is null for eval calls; this metric is not measurable from the event table",
    }
    if sids:
        try:
            tool_rows = await _sql_rows(
                sids,
                "SELECT tool, count(*) AS calls, count(*) FILTER (WHERE status='error') AS errs "
                "FROM src.events WHERE kind='call' GROUP BY tool ORDER BY calls DESC",
            )
            aggregated: dict[str, dict[str, int]] = {}
            for row in tool_rows:
                key = str(row.get("tool") or "unknown")
                entry = aggregated.setdefault(key, {"calls": 0, "errors": 0})
                entry["calls"] += int(row.get("calls") or 0)
                entry["errors"] += int(row.get("errs") or 0)
            for key, entry in sorted(aggregated.items(), key=lambda item: -item[1]["calls"]):
                tools.append(
                    {
                        "tool": key,
                        "calls": entry["calls"],
                        "errors": entry["errors"],
                        "error_rate": _ratio(entry["errors"], entry["calls"]),
                    }
                )
        except Exception as exc:  # noqa: BLE001 - the collector reports, never blocks
            tools = [{"error": f"tool query failed: {exc}"}]

        try:
            shake_rows = await _sql_rows(
                sids,
                "SELECT count(*) AS shaken, (SELECT count(*) FROM src.entries) AS entries "
                "FROM (SELECT CAST(json AS VARCHAR) AS j FROM src.entries) "
                "WHERE j LIKE '%shaken ~%'",
            )
            if shake_rows:
                shaken = sum(int(row.get("shaken") or 0) for row in shake_rows)
                entries = sum(int(row.get("entries") or 0) for row in shake_rows)
                shake = {"shaken": shaken, "entries": entries, "ratio": _ratio(shaken, entries)}
        except Exception as exc:  # noqa: BLE001
            shake["error"] = f"shake query failed: {exc}"

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "window_days": WINDOW_DAYS,
        "sessions": {
            "total": len(recent),
            "private_tmp": private_tmp,
            "private_tmp_share": _ratio(private_tmp, len(recent)),
            "status": statuses,
            "median_assistant_turns": median_turns,
            "large_files": sum(1 for row in recent if int(row.get("size") or 0) > 5_000_000),
        },
        "tools": tools,
        "context_shake": shake,
        "eval_file_reads": eval_reads,
        "limitations": [
            "Trace-level labels (premature endings, incident rates) are computed by the weekly reviewer.",
            "eval_file_reads is not measurable from the event table; the weekly reviewer labels traces.",
            "A model or provider change invalidates comparisons across the boundary.",
        ],
    }

    target = PCH_HOME / "data" / f"metrics-{date.today().isoformat()}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    write(str(target), json.dumps(payload, ensure_ascii=False, indent=2))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"\nwrote {target}")
    return payload


await collect()