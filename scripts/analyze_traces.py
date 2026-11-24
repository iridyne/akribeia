#!/usr/bin/env python3
"""Privacy-safe session trace analyzer for Akribeia.

Computes structural telemetry from OMP-format JSONL coding-agent traces without
ever emitting raw prompts, user text, repository names, secrets, or local paths.
Supports deterministic bootstrap 95% confidence intervals (stdlib only).

Usage:
    python3 scripts/analyze_traces.py examples/demo-sessions
    python3 scripts/analyze_traces.py examples/demo-sessions --markdown
    python3 scripts/analyze_traces.py ~/.omp/agent/sessions --since 2026-09-01 --markdown
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import random
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SessionSummary:
    date: str
    is_private_tmp: bool
    user_turns: int
    assistant_turns: int
    tool_calls: int
    tool_errors: int
    aborted: bool
    premature_end: bool
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    reasoning_tokens: int
    user_chars: int
    assistant_chars: int
    tool_result_chars: int
    prompt_digests: int
    shaken_entries: int
    total_entries: int
    file_bytes: int


def _content_chars(content: Any) -> int:
    if content is None:
        return 0
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        total = 0
        for item in content:
            if isinstance(item, str):
                total += len(item)
            elif isinstance(item, dict):
                if isinstance(item.get("text"), str):
                    total += len(item["text"])
                elif isinstance(item.get("thinking"), str):
                    total += len(item["thinking"])
                elif "arguments" in item:
                    total += len(str(item["arguments"]))
        return total
    if isinstance(content, dict):
        return len(str(content))
    return 0


def _extract_date(ts: Any) -> str:
    if isinstance(ts, str) and len(ts) >= 10:
        return ts[:10]
    return ""


def parse_session_file(path: Path) -> tuple[SessionSummary | None, dict[str, list[int]]]:
    """Parse one JSONL session into aggregate metrics + per-tool [calls, errors, chars]."""
    tool_stats: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0, 0])
    session_date = ""
    is_private_tmp = "--private-tmp--" in path.parts
    user_turns = 0
    assistant_turns = 0
    tool_calls = 0
    tool_errors = 0
    aborted = False
    input_tokens = 0
    output_tokens = 0
    cache_read_tokens = 0
    cache_write_tokens = 0
    reasoning_tokens = 0
    user_chars = 0
    assistant_chars = 0
    tool_result_chars = 0
    digests: set[str] = set()
    shaken_entries = 0
    total_entries = 0
    last_role = ""
    last_stop_reason = ""
    last_assistant_has_text = False

    try:
        file_bytes = path.stat().st_size
    except OSError:
        return None, {}

    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if not line.strip():
                continue
            total_entries += 1
            if "shaken ~" in line:
                shaken_entries += 1
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            etype = obj.get("type")
            if not session_date:
                session_date = _extract_date(obj.get("timestamp"))

            if etype == "session":
                cwd = str(obj.get("cwd", ""))
                if "/private/tmp" in cwd or cwd.startswith("/tmp"):
                    is_private_tmp = True
                if not session_date:
                    session_date = _extract_date(obj.get("timestamp"))
            elif etype in ("custom", "custom_message"):
                ctype = str(obj.get("customType", ""))
                if ctype == "system-prompt-digest":
                    data = obj.get("data")
                    if isinstance(data, dict):
                        digest = str(data.get("digest") or data.get("hash") or data.get("sha256") or "")
                        if digest:
                            digests.add(digest)
                    elif isinstance(data, str) and data:
                        digests.add(data[:32])
            elif etype == "message":
                msg = obj.get("message")
                if not isinstance(msg, dict):
                    continue
                role = str(msg.get("role", ""))
                last_role = role
                chars = _content_chars(msg.get("content"))

                if role == "user":
                    user_turns += 1
                    user_chars += chars
                elif role == "assistant":
                    assistant_turns += 1
                    assistant_chars += chars
                    stop_reason = str(msg.get("stopReason", ""))
                    last_stop_reason = stop_reason
                    if stop_reason in {"aborted", "error"}:
                        aborted = True
                    # Check whether final assistant message emitted non-empty text
                    content = msg.get("content")
                    if isinstance(content, str):
                        last_assistant_has_text = bool(content.strip())
                    elif isinstance(content, list):
                        last_assistant_has_text = any(
                            isinstance(b, dict) and b.get("type") == "text" and bool(str(b.get("text", "")).strip())
                            for b in content
                        )
                    else:
                        last_assistant_has_text = False

                    usage = msg.get("usage")
                    if isinstance(usage, dict):
                        input_tokens += int(usage.get("input") or 0)
                        output_tokens += int(usage.get("output") or 0)
                        cache_read_tokens += int(usage.get("cacheRead") or 0)
                        cache_write_tokens += int(usage.get("cacheWrite") or 0)
                        reasoning_tokens += int(usage.get("reasoningTokens") or 0)
                elif role == "toolResult":
                    tool_calls += 1
                    tool_result_chars += chars
                    tname = str(msg.get("toolName") or "unknown")
                    is_err = bool(msg.get("isError"))
                    if is_err:
                        tool_errors += 1
                    tool_stats[tname][0] += 1
                    tool_stats[tname][1] += 1 if is_err else 0
                    tool_stats[tname][2] += chars

    if assistant_turns == 0 and user_turns == 0:
        return None, {}

    premature_end = (
        not aborted
        and assistant_turns > 0
        and (last_role == "toolResult" or (last_role == "assistant" and last_stop_reason == "toolUse" and not last_assistant_has_text))
    )

    return (
        SessionSummary(
            date=session_date or "unknown",
            is_private_tmp=is_private_tmp,
            user_turns=user_turns,
            assistant_turns=assistant_turns,
            tool_calls=tool_calls,
            tool_errors=tool_errors,
            aborted=aborted,
            premature_end=premature_end,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            reasoning_tokens=reasoning_tokens,
            user_chars=user_chars,
            assistant_chars=assistant_chars,
            tool_result_chars=tool_result_chars,
            prompt_digests=len(digests),
            shaken_entries=shaken_entries,
            total_entries=total_entries,
            file_bytes=file_bytes,
        ),
        tool_stats,
    )


def bootstrap_ci(values: list[float], *, resamples: int = 1000, seed: int = 42) -> tuple[float, float, float]:
    """Deterministic percentile bootstrap 95% CI for the mean."""
    if not values:
        return 0.0, 0.0, 0.0
    mean = sum(values) / len(values)
    if len(values) == 1:
        return mean, mean, mean
    rng = random.Random(seed)
    n = len(values)
    means: list[float] = []
    for _ in range(resamples):
        sample_sum = sum(values[rng.randrange(n)] for _ in range(n))
        means.append(sample_sum / n)
    means.sort()
    lo = means[int(0.025 * resamples)]
    hi = means[min(resamples - 1, int(0.975 * resamples))]
    return mean, lo, hi


def percentile(sorted_vals: list[int | float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    return float(sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f))


def analyze_directory(
    root: Path,
    *,
    since: str | None = None,
    min_turns: int = 1,
    seed: int = 42,
) -> dict[str, Any]:
    files = sorted(p for p in root.rglob("*.jsonl") if p.is_file())
    sessions: list[SessionSummary] = []
    agg_tools: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0, 0])

    for path in files:
        summary, tstats = parse_session_file(path)
        if summary is None:
            continue
        if since and summary.date != "unknown" and summary.date < since:
            continue
        if summary.assistant_turns < min_turns:
            continue
        sessions.append(summary)
        for tname, (calls, errs, chars) in tstats.items():
            agg_tools[tname][0] += calls
            agg_tools[tname][1] += errs
            agg_tools[tname][2] += chars

    n = len(sessions)
    dates = sorted(s.date for s in sessions if s.date != "unknown")
    turns = sorted(s.assistant_turns for s in sessions)
    tool_counts = sorted(s.tool_calls for s in sessions)

    tot_user_chars = sum(s.user_chars for s in sessions)
    tot_asst_chars = sum(s.assistant_chars for s in sessions)
    tot_tool_chars = sum(s.tool_result_chars for s in sessions)
    tot_chars = tot_user_chars + tot_asst_chars + tot_tool_chars

    tot_in = sum(s.input_tokens for s in sessions)
    tot_out = sum(s.output_tokens for s in sessions)
    tot_cr = sum(s.cache_read_tokens for s in sessions)
    tot_cw = sum(s.cache_write_tokens for s in sessions)
    tot_prompt_tokens = tot_in + tot_cr + tot_cw

    tot_tool_calls = sum(s.tool_calls for s in sessions)
    tot_tool_errors = sum(s.tool_errors for s in sessions)
    tot_entries = sum(s.total_entries for s in sessions)
    tot_shaken = sum(s.shaken_entries for s in sessions)

    # Per-session ratios for bootstrap CIs
    tool_char_shares = [
        s.tool_result_chars / (s.user_chars + s.assistant_chars + s.tool_result_chars)
        for s in sessions
        if (s.user_chars + s.assistant_chars + s.tool_result_chars) > 0
    ]
    cache_hit_rates = [
        s.cache_read_tokens / (s.input_tokens + s.cache_read_tokens + s.cache_write_tokens)
        for s in sessions
        if (s.input_tokens + s.cache_read_tokens + s.cache_write_tokens) > 0
    ]
    err_rates_per_session = [s.tool_errors / s.tool_calls for s in sessions if s.tool_calls > 0]

    # Compare stable prompt digest (<=1) vs multi-digest (>1) cache hit rate
    stable_cache = [
        s.cache_read_tokens / (s.input_tokens + s.cache_read_tokens + s.cache_write_tokens)
        for s in sessions
        if s.prompt_digests == 1 and (s.input_tokens + s.cache_read_tokens + s.cache_write_tokens) > 0
    ]
    drifted_cache = [
        s.cache_read_tokens / (s.input_tokens + s.cache_read_tokens + s.cache_write_tokens)
        for s in sessions
        if s.prompt_digests > 1 and (s.input_tokens + s.cache_read_tokens + s.cache_write_tokens) > 0
    ]

    # Heavy sessions (>=10 assistant turns) vs short sessions (<10)
    heavy = [s for s in sessions if s.assistant_turns >= 10]
    short = [s for s in sessions if s.assistant_turns < 10]

    def _group_stats(group: list[SessionSummary]) -> dict[str, Any]:
        if not group:
            return {"sessions": 0}
        g_calls = sum(s.tool_calls for s in group)
        g_errs = sum(s.tool_errors for s in group)
        g_chars = sum(s.user_chars + s.assistant_chars + s.tool_result_chars for s in group)
        g_tchars = sum(s.tool_result_chars for s in group)
        g_ptok = sum(s.input_tokens + s.cache_read_tokens + s.cache_write_tokens for s in group)
        g_cr = sum(s.cache_read_tokens for s in group)
        return {
            "sessions": len(group),
            "median_assistant_turns": round(statistics.median(s.assistant_turns for s in group), 1),
            "tool_calls": g_calls,
            "tool_error_rate": round(g_errs / g_calls, 4) if g_calls else 0.0,
            "tool_output_char_share": round(g_tchars / g_chars, 4) if g_chars else 0.0,
            "cache_hit_rate": round(g_cr / g_ptok, 4) if g_ptok else 0.0,
            "abort_rate": round(sum(1 for s in group if s.aborted) / len(group), 4),
            "premature_end_rate": round(sum(1 for s in group if s.premature_end) / len(group), 4),
        }

    top_tools = []
    for name, (calls, errs, chars) in sorted(agg_tools.items(), key=lambda kv: -kv[1][0])[:12]:
        top_tools.append(
            {
                "tool": name,
                "calls": calls,
                "errors": errs,
                "error_rate": round(errs / calls, 4) if calls else 0.0,
                "char_share_of_tool_output": round(chars / tot_tool_chars, 4) if tot_tool_chars else 0.0,
            }
        )

    tc_mean, tc_lo, tc_hi = bootstrap_ci(tool_char_shares, seed=seed)
    ch_mean, ch_lo, ch_hi = bootstrap_ci(cache_hit_rates, seed=seed)
    er_mean, er_lo, er_hi = bootstrap_ci(err_rates_per_session, seed=seed)
    st_mean, st_lo, st_hi = bootstrap_ci(stable_cache, seed=seed)
    dr_mean, dr_lo, dr_hi = bootstrap_ci(drifted_cache, seed=seed)

    return {
        "window": {
            "first_date": dates[0] if dates else "unknown",
            "last_date": dates[-1] if dates else "unknown",
            "since_filter": since,
            "min_turns": min_turns,
        },
        "sessions": {
            "total": n,
            "private_tmp": sum(1 for s in sessions if s.is_private_tmp),
            "private_tmp_share": round(sum(1 for s in sessions if s.is_private_tmp) / n, 4) if n else 0.0,
            "aborted": sum(1 for s in sessions if s.aborted),
            "abort_rate": round(sum(1 for s in sessions if s.aborted) / n, 4) if n else 0.0,
            "premature_end": sum(1 for s in sessions if s.premature_end),
            "premature_end_rate": round(sum(1 for s in sessions if s.premature_end) / n, 4) if n else 0.0,
            "large_over_5mb": sum(1 for s in sessions if s.file_bytes > 5_000_000),
            "turns_p50": round(percentile(turns, 0.5), 1),
            "turns_p90": round(percentile(turns, 0.9), 1),
            "turns_p99": round(percentile(turns, 0.99), 1),
            "tool_calls_p50": round(percentile(tool_counts, 0.5), 1),
            "tool_calls_p90": round(percentile(tool_counts, 0.9), 1),
        },
        "context_composition": {
            "total_chars": tot_chars,
            "user_char_share": round(tot_user_chars / tot_chars, 4) if tot_chars else 0.0,
            "assistant_char_share": round(tot_asst_chars / tot_chars, 4) if tot_chars else 0.0,
            "tool_result_char_share_pooled": round(tot_tool_chars / tot_chars, 4) if tot_chars else 0.0,
            "tool_result_char_share_session_mean": round(tc_mean, 4),
            "tool_result_char_share_ci95": [round(tc_lo, 4), round(tc_hi, 4)],
            "context_shake_entries": tot_shaken,
            "total_entries": tot_entries,
            "context_shake_ratio": round(tot_shaken / tot_entries, 4) if tot_entries else 0.0,
        },
        "tokens_and_cache": {
            "total_prompt_tokens": tot_prompt_tokens,
            "total_output_tokens": tot_out,
            "pooled_cache_hit_rate": round(tot_cr / tot_prompt_tokens, 4) if tot_prompt_tokens else 0.0,
            "session_cache_hit_mean": round(ch_mean, 4),
            "session_cache_hit_ci95": [round(ch_lo, 4), round(ch_hi, 4)],
            "single_digest_sessions": len(stable_cache),
            "single_digest_cache_mean": round(st_mean, 4),
            "single_digest_cache_ci95": [round(st_lo, 4), round(st_hi, 4)],
            "multi_digest_sessions": len(drifted_cache),
            "multi_digest_cache_mean": round(dr_mean, 4),
            "multi_digest_cache_ci95": [round(dr_lo, 4), round(dr_hi, 4)],
        },
        "tools": {
            "total_calls": tot_tool_calls,
            "total_errors": tot_tool_errors,
            "pooled_error_rate": round(tot_tool_errors / tot_tool_calls, 4) if tot_tool_calls else 0.0,
            "session_error_rate_mean": round(er_mean, 4),
            "session_error_rate_ci95": [round(er_lo, 4), round(er_hi, 4)],
            "by_tool": top_tools,
        },
        "stratification": {
            "heavy_ge_10_turns": _group_stats(heavy),
            "short_lt_10_turns": _group_stats(short),
            "named_project": _group_stats([s for s in sessions if not s.is_private_tmp]),
            "private_tmp": _group_stats([s for s in sessions if s.is_private_tmp]),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    w = report["window"]
    s = report["sessions"]
    c = report["context_composition"]
    t = report["tokens_and_cache"]
    tl = report["tools"]
    st = report["stratification"]

    lines = [
        "## Trace Telemetry Summary",
        "",
        f"- **Window:** `{w['first_date']}` to `{w['last_date']}` (`min_turns={w['min_turns']}`)",
        f"- **Sessions analyzed:** `{s['total']}` (named project `{s['total'] - s['private_tmp']}`, `--private-tmp--` `{s['private_tmp']}` / `{s['private_tmp_share']*100:.1f}%`)",
        f"- **Assistant turns:** P50 `{s['turns_p50']}` / P90 `{s['turns_p90']}` / P99 `{s['turns_p99']}` (sessions > 5 MB: `{s['large_over_5mb']}`)",
        f"- **Context byte share (pooled):** tool outputs `{c['tool_result_char_share_pooled']*100:.1f}%`, assistant `{c['assistant_char_share']*100:.1f}%`, user `{c['user_char_share']*100:.1f}%` (per-session tool share `{c['tool_result_char_share_session_mean']*100:.1f}%`, 95% CI `[{c['tool_result_char_share_ci95'][0]*100:.1f}%, {c['tool_result_char_share_ci95'][1]*100:.1f}%]`)",
        f"- **Prompt cache hit rate (pooled):** `{t['pooled_cache_hit_rate']*100:.2f}%` across `{t['total_prompt_tokens']:,}` prompt tokens (per-session mean `{t['session_cache_hit_mean']*100:.1f}%`, 95% CI `[{t['session_cache_hit_ci95'][0]*100:.1f}%, {t['session_cache_hit_ci95'][1]*100:.1f}%]`)",
        f"- **Tool surface:** `{tl['total_calls']:,}` calls, `{tl['total_errors']:,}` errors (`{tl['pooled_error_rate']*100:.2f}%` pooled)",
        "",
        "### Stratification (Heavy >=10 turns vs Short <10 turns)",
        "",
        "| Cohort | Sessions | Median turns | Tool calls | Tool error rate | Tool output share | Cache hit rate | Abort rate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, key in [
        ("Heavy (>=10 turns)", "heavy_ge_10_turns"),
        ("Short (<10 turns)", "short_lt_10_turns"),
        ("Named project", "named_project"),
        ("Ephemeral (`--private-tmp--`)", "private_tmp"),
    ]:
        g = st[key]
        if g.get("sessions", 0) == 0:
            continue
        lines.append(
            f"| {label} | {g['sessions']} | {g['median_assistant_turns']} | {g['tool_calls']:,} | "
            f"{g['tool_error_rate']*100:.2f}% | {g['tool_output_char_share']*100:.1f}% | "
            f"{g['cache_hit_rate']*100:.1f}% | {g['abort_rate']*100:.1f}% |"
        )

    lines.extend(
        [
            "",
            "### Top Tools by Call Volume",
            "",
            "| Tool | Calls | Errors | Error rate | Share of tool output chars |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in tl["by_tool"]:
        lines.append(
            f"| `{row['tool']}` | {row['calls']:,} | {row['errors']:,} | "
            f"{row['error_rate']*100:.2f}% | {row['char_share_of_tool_output']*100:.1f}% |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sessions_dir", type=Path, help="directory containing JSONL trace files")
    parser.add_argument("--since", type=str, default=None, help="include sessions on or after YYYY-MM-DD")
    parser.add_argument("--min-turns", type=int, default=1, help="minimum assistant turns per session")
    parser.add_argument("--seed", type=int, default=42, help="bootstrap PRNG seed")
    parser.add_argument("--markdown", action="store_true", help="render Markdown report instead of JSON")
    args = parser.parse_args()

    if not args.sessions_dir.exists():
        print(f"error: sessions_dir not found: {args.sessions_dir}", file=sys.stderr)
        return 1

    report = analyze_directory(args.sessions_dir, since=args.since, min_turns=args.min_turns, seed=args.seed)
    if args.markdown:
        print(render_markdown(report))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
