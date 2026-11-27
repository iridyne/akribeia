#!/usr/bin/env python3
"""Privacy-safe multi-runtime session trace analyzer for Akribeia.

Computes structural telemetry from OMP, Claude Code (`~/.claude/projects`), and
OpenAI Codex CLI (`~/.codex/sessions`) JSONL traces without ever emitting raw
prompts, user text, repository names, secrets, or local paths.
Supports deterministic bootstrap 95% confidence intervals (stdlib only).

Usage:
    python3 scripts/analyze_traces.py examples/demo-sessions
    python3 scripts/analyze_traces.py ~/.claude/projects --markdown
    python3 scripts/analyze_traces.py ~/.codex/sessions --since 2026-09-01 --markdown
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import random
import re
import statistics
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Uncalibrated bilingual repair-turn cues (R4):
# Explicitly labeled uncalibrated until validated against >=20 human-labeled incidents (docs/program.md §2, R4).
ZH_REPAIR_CUES_RE = re.compile(
    r"(?:不对|错了|不是这个意思|我说的是|重来|重新做|别用|不要用|不要这样|搞错了|理解错了|不是让你|跑偏|偏题|先停|停一下|你没看|不是那个)"
)
EN_REPAIR_CUES_RE = re.compile(
    r"\b(?:no,\s*i\s+(?:said|meant)|that'?s\s+(?:wrong|not\s+right)|not\s+what\s+i\s+asked|stop\s+doing|wrong\s+(?:file|repo|path)|undo\s+that|revert\s+that|start\s+over)\b",
    re.IGNORECASE,
)


@dataclass
class SessionSummary:
    date: str
    runtime: str
    is_private_tmp: bool
    user_turns: int
    assistant_turns: int
    tool_calls: int
    tool_errors: int
    aborted: bool
    premature_end: bool
    completed: bool
    repair_turns: int
    repair_cue_zh_turns: int
    repair_cue_en_turns: int
    post_abort_followups: int
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


def _extract_plain_text(content: Any) -> str:
    """Extract user text internally for heuristic classification; never emitted in output (D-005)."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") in {None, "text", "input_text", "output_text"}:
                if isinstance(item.get("text"), str):
                    parts.append(item["text"])
        return "\n".join(parts)
    if isinstance(content, dict) and isinstance(content.get("text"), str):
        return content["text"]
    return ""


def classify_repair_turn(text: str, *, after_abort: bool = False) -> tuple[bool, bool, bool, bool]:
    """Return (is_repair, zh_cue, en_cue, post_abort_followup) without storing or emitting raw text."""
    zh = bool(ZH_REPAIR_CUES_RE.search(text))
    en = bool(EN_REPAIR_CUES_RE.search(text))
    post_abort = bool(after_abort)
    return (zh or en or post_abort), zh, en, post_abort


def evaluate_repair_calibration(
    predictions: Sequence[bool],
    labels: Sequence[bool],
    *,
    min_samples: int = 20,
    min_kappa: float = 0.6,
) -> dict[str, Any]:
    """Compute agreement & Cohen's kappa for R4 repair-turn heuristic calibration."""
    if len(predictions) != len(labels):
        raise ValueError("predictions and labels must have equal length")
    n = len(labels)
    if n == 0:
        return {
            "n": 0,
            "tp": 0,
            "fp": 0,
            "fn": 0,
            "tn": 0,
            "agreement": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "cohen_kappa": 0.0,
            "calibrated": False,
        }
    tp = sum(1 for p, y in zip(predictions, labels) if p and y)
    fp = sum(1 for p, y in zip(predictions, labels) if p and not y)
    fn = sum(1 for p, y in zip(predictions, labels) if not p and y)
    tn = sum(1 for p, y in zip(predictions, labels) if not p and not y)
    po = (tp + tn) / n
    p_yes = ((tp + fp) / n) * ((tp + fn) / n)
    p_no = ((fn + tn) / n) * ((fp + tn) / n)
    pe = p_yes + p_no
    kappa = 1.0 if abs(1.0 - pe) < 1e-12 else (po - pe) / (1.0 - pe)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "n": n,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "agreement": round(po, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "cohen_kappa": round(kappa, 4),
        "calibrated": bool(n >= min_samples and kappa >= min_kappa),
    }


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
                elif item.get("type") == "tool_use" and "input" in item:
                    total += len(str(item["input"]))
                elif item.get("type") == "tool_result" and "content" in item:
                    total += _content_chars(item.get("content"))
        return total
    if isinstance(content, dict):
        return len(str(content))
    return 0


def _extract_date(ts: Any) -> str:
    if isinstance(ts, str) and len(ts) >= 10:
        return ts[:10]
    return ""


def _is_tmp_cwd(cwd: Any) -> bool:
    if not isinstance(cwd, str) or not cwd:
        return False
    return "/private/tmp" in cwd or cwd.startswith("/tmp")


def _detect_trace_format(records: list[dict[str, Any]], requested: str = "auto") -> str:
    if requested != "auto":
        return requested
    for obj in records:
        etype = obj.get("type")
        if etype in {"session", "custom", "custom_message"}:
            return "omp"
        if etype == "message" and isinstance(obj.get("message"), dict):
            return "omp"
        if etype in {"session_meta", "response_item", "event_msg"} and isinstance(obj.get("payload"), dict):
            return "codex"
        if etype in {"user", "assistant"} and isinstance(obj.get("message"), dict):
            return "claude"
    return "omp"


def _codex_output_is_error(payload: dict[str, Any], output_val: Any) -> bool:
    if payload.get("is_error") is True:
        return True
    text = output_val if isinstance(output_val, str) else json.dumps(output_val, ensure_ascii=False)
    try:
        parsed = json.loads(text) if isinstance(output_val, str) else output_val
        if isinstance(parsed, dict):
            meta = parsed.get("metadata")
            if isinstance(meta, dict):
                code = meta.get("exit_code")
                if isinstance(code, int) and code != 0:
                    return True
    except (json.JSONDecodeError, TypeError):
        pass
    m = re.search(r"(?:Exit code|Process exited with code):\s*(-?\d+)", text)
    if m and int(m.group(1)) != 0:
        return True
    return False


def parse_session_file(
    path: Path,
    *,
    fmt: str = "auto",
) -> tuple[SessionSummary | None, dict[str, list[int]]]:
    """Parse one OMP, Claude Code, or Codex CLI JSONL trace into aggregate metrics."""
    tool_stats: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0, 0])
    session_date = ""
    is_private_tmp = "--private-tmp--" in path.parts
    user_turns = 0
    assistant_turns = 0
    tool_calls = 0
    tool_errors = 0
    aborted = False
    repair_turns = 0
    repair_cue_zh_turns = 0
    repair_cue_en_turns = 0
    post_abort_followups = 0
    prev_assistant_aborted = False
    last_tool_is_error = False
    input_tokens = 0
    output_tokens = 0
    cache_read_tokens = 0
    cache_write_tokens = 0
    reasoning_tokens = 0
    codex_last_usage_seen = False
    codex_fallback_total_usage: dict[str, int] | None = None
    user_chars = 0
    assistant_chars = 0
    tool_result_chars = 0
    digests: set[str] = set()
    shaken_entries = 0
    total_entries = 0
    last_role = ""
    last_stop_reason = ""
    last_assistant_has_text = False
    tool_id_to_name: dict[str, str] = {}
    codex_turn_has_assistant_msg = False

    try:
        file_bytes = path.stat().st_size
    except OSError:
        return None, {}

    records: list[dict[str, Any]] = []
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
            if isinstance(obj, dict):
                records.append(obj)

    if not records:
        return None, {}

    detected = _detect_trace_format(records, requested=fmt)
    runtime_name = {"omp": "omp", "claude": "claude_code", "codex": "codex"}.get(detected, detected)

    def _record_user_turn(plain_text: str, chars: int) -> None:
        nonlocal user_turns, user_chars, last_role, prev_assistant_aborted, codex_turn_has_assistant_msg
        nonlocal repair_turns, repair_cue_zh_turns, repair_cue_en_turns, post_abort_followups
        user_turns += 1
        user_chars += chars
        last_role = "user"
        codex_turn_has_assistant_msg = False
        if user_turns >= 2:
            is_rep, zh_hit, en_hit, post_ab = classify_repair_turn(
                plain_text, after_abort=prev_assistant_aborted
            )
            if is_rep:
                repair_turns += 1
            if zh_hit:
                repair_cue_zh_turns += 1
            if en_hit:
                repair_cue_en_turns += 1
            if post_ab:
                post_abort_followups += 1
        prev_assistant_aborted = False

    def _record_tool_result(tname: str, is_err: bool, chars: int) -> None:
        nonlocal tool_calls, tool_errors, tool_result_chars, last_role, last_tool_is_error, codex_turn_has_assistant_msg
        tool_calls += 1
        tool_result_chars += chars
        last_role = "toolResult"
        last_tool_is_error = is_err
        codex_turn_has_assistant_msg = False
        if is_err:
            tool_errors += 1
        tool_stats[tname][0] += 1
        tool_stats[tname][1] += 1 if is_err else 0
        tool_stats[tname][2] += chars

    for obj in records:
        etype = obj.get("type")
        if not session_date:
            session_date = _extract_date(obj.get("timestamp"))
        if _is_tmp_cwd(obj.get("cwd")):
            is_private_tmp = True

        if detected == "omp":
            if etype == "session":
                if _is_tmp_cwd(obj.get("cwd")):
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
                chars = _content_chars(msg.get("content"))

                if role == "user":
                    _record_user_turn(_extract_plain_text(msg.get("content")), chars)
                elif role == "assistant":
                    assistant_turns += 1
                    assistant_chars += chars
                    last_role = "assistant"
                    stop_reason = str(msg.get("stopReason", ""))
                    last_stop_reason = stop_reason
                    if stop_reason in {"aborted", "error"}:
                        aborted = True
                        prev_assistant_aborted = True
                    else:
                        prev_assistant_aborted = False
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
                    tname = str(msg.get("toolName") or "unknown")
                    _record_tool_result(tname, bool(msg.get("isError")), chars)

        elif detected == "claude":
            if obj.get("isSidechain") is True:
                continue
            if etype == "user":
                if obj.get("isMeta") is True:
                    continue
                msg = obj.get("message")
                if not isinstance(msg, dict):
                    continue
                content = msg.get("content")
                if isinstance(content, list):
                    tool_blocks = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_result"]
                    non_tool_blocks = [b for b in content if not (isinstance(b, dict) and b.get("type") == "tool_result")]
                    for b in tool_blocks:
                        tid = str(b.get("tool_use_id") or "")
                        tname = tool_id_to_name.get(tid, "unknown")
                        _record_tool_result(tname, bool(b.get("is_error")), _content_chars(b.get("content")))
                    if non_tool_blocks:
                        plain = _extract_plain_text(non_tool_blocks)
                        if plain.strip():
                            _record_user_turn(plain, _content_chars(non_tool_blocks))
                else:
                    plain = _extract_plain_text(content)
                    if plain.strip():
                        _record_user_turn(plain, _content_chars(content))
            elif etype == "assistant":
                msg = obj.get("message")
                if not isinstance(msg, dict):
                    continue
                assistant_turns += 1
                last_role = "assistant"
                content = msg.get("content")
                assistant_chars += _content_chars(content)
                if isinstance(content, list):
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "tool_use":
                            tid = str(b.get("id") or "")
                            tname = str(b.get("name") or "unknown")
                            if tid:
                                tool_id_to_name[tid] = tname
                    last_assistant_has_text = any(
                        isinstance(b, dict) and b.get("type") == "text" and bool(str(b.get("text", "")).strip())
                        for b in content
                    )
                elif isinstance(content, str):
                    last_assistant_has_text = bool(content.strip())
                else:
                    last_assistant_has_text = False

                raw_stop = str(msg.get("stop_reason") or msg.get("stopReason") or "")
                stop_reason = "toolUse" if raw_stop == "tool_use" else raw_stop
                last_stop_reason = stop_reason
                if stop_reason in {"aborted", "error", "refusal"}:
                    aborted = True
                    prev_assistant_aborted = True
                else:
                    prev_assistant_aborted = False

                usage = msg.get("usage")
                if isinstance(usage, dict):
                    input_tokens += int(usage.get("input_tokens") or usage.get("input") or 0)
                    output_tokens += int(usage.get("output_tokens") or usage.get("output") or 0)
                    cache_read_tokens += int(usage.get("cache_read_input_tokens") or usage.get("cacheRead") or 0)
                    cache_write_tokens += int(usage.get("cache_creation_input_tokens") or usage.get("cacheWrite") or 0)

        elif detected == "codex":
            payload = obj.get("payload")
            if not isinstance(payload, dict):
                continue
            if etype == "session_meta":
                if _is_tmp_cwd(payload.get("cwd")):
                    is_private_tmp = True
                if not session_date:
                    session_date = _extract_date(payload.get("timestamp"))
            elif etype == "response_item":
                ptype = payload.get("type")
                if ptype == "message":
                    role = str(payload.get("role", ""))
                    content = payload.get("content")
                    chars = _content_chars(content)
                    if role == "user":
                        plain = _extract_plain_text(content)
                        if plain.strip():
                            _record_user_turn(plain, chars)
                    elif role == "assistant":
                        assistant_turns += 1
                        codex_turn_has_assistant_msg = True
                        assistant_chars += chars
                        last_role = "assistant"
                        last_stop_reason = "stop"
                        prev_assistant_aborted = False
                        plain = _extract_plain_text(content)
                        last_assistant_has_text = bool(plain.strip())
                elif ptype in {"function_call", "custom_tool_call"}:
                    if not codex_turn_has_assistant_msg:
                        assistant_turns += 1
                        codex_turn_has_assistant_msg = True
                    last_role = "assistant"
                    last_stop_reason = "toolUse"
                    last_assistant_has_text = False
                    prev_assistant_aborted = False
                    cid = str(payload.get("call_id") or "")
                    tname = str(payload.get("name") or "custom_tool")
                    if cid:
                        tool_id_to_name[cid] = tname
                    arg_blob = payload.get("arguments") if "arguments" in payload else payload.get("input", "")
                    assistant_chars += len(str(arg_blob))
                elif ptype in {"function_call_output", "custom_tool_call_output"}:
                    cid = str(payload.get("call_id") or "")
                    tname = tool_id_to_name.get(cid, "unknown")
                    out_val = payload.get("output")
                    is_err = _codex_output_is_error(payload, out_val)
                    chars = _content_chars(out_val) if not isinstance(out_val, str) else len(out_val)
                    _record_tool_result(tname, is_err, chars)
            elif etype == "event_msg":
                ptype = payload.get("type")
                if ptype == "turn_aborted":
                    aborted = True
                    prev_assistant_aborted = True
                    last_stop_reason = "aborted"
                elif ptype == "token_count":
                    info = payload.get("info")
                    if isinstance(info, dict):
                        last_u = info.get("last_token_usage")
                        tot_u = info.get("total_token_usage")
                        if isinstance(last_u, dict):
                            codex_last_usage_seen = True
                            raw_in = int(last_u.get("input_tokens") or 0)
                            cached_in = int(last_u.get("cached_input_tokens") or 0)
                            # OpenAI input_tokens includes cached_input_tokens; store uncached delta in input_tokens
                            # so total_prompt_tokens (= input + cache_read + cache_write) is not double-counted.
                            input_tokens += max(0, raw_in - cached_in)
                            output_tokens += int(last_u.get("output_tokens") or 0)
                            cache_read_tokens += cached_in
                            reasoning_tokens += int(last_u.get("reasoning_output_tokens") or 0)
                        elif isinstance(tot_u, dict):
                            raw_in = int(tot_u.get("input_tokens") or 0)
                            cached_in = int(tot_u.get("cached_input_tokens") or 0)
                            codex_fallback_total_usage = {
                                "input": max(0, raw_in - cached_in),
                                "output": int(tot_u.get("output_tokens") or 0),
                                "cache_read": cached_in,
                                "reasoning": int(tot_u.get("reasoning_output_tokens") or 0),
                            }

    if not codex_last_usage_seen and codex_fallback_total_usage is not None:
        input_tokens = codex_fallback_total_usage["input"]
        output_tokens = codex_fallback_total_usage["output"]
        cache_read_tokens = codex_fallback_total_usage["cache_read"]
        reasoning_tokens = codex_fallback_total_usage["reasoning"]

    if assistant_turns == 0 and user_turns == 0:
        return None, {}

    premature_end = (
        not aborted
        and assistant_turns > 0
        and (last_role == "toolResult" or (last_role == "assistant" and last_stop_reason == "toolUse" and not last_assistant_has_text))
    )
    # Completed session proxy (docs/program.md §2): final assistant turn emitted non-empty text
    # and the final tool result was not an error (even if an earlier turn had an abort that was recovered).
    completed = (
        assistant_turns > 0
        and last_role == "assistant"
        and last_stop_reason not in {"aborted", "error"}
        and last_assistant_has_text
        and not last_tool_is_error
    )

    return (
        SessionSummary(
            date=session_date or "unknown",
            runtime=runtime_name,
            is_private_tmp=is_private_tmp,
            user_turns=user_turns,
            assistant_turns=assistant_turns,
            tool_calls=tool_calls,
            tool_errors=tool_errors,
            aborted=aborted,
            premature_end=premature_end,
            completed=completed,
            repair_turns=repair_turns,
            repair_cue_zh_turns=repair_cue_zh_turns,
            repair_cue_en_turns=repair_cue_en_turns,
            post_abort_followups=post_abort_followups,
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
    fmt: str = "auto",
) -> dict[str, Any]:
    files = sorted(p for p in root.rglob("*.jsonl") if p.is_file())
    sessions: list[SessionSummary] = []
    agg_tools: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0, 0])

    for path in files:
        summary, tstats = parse_session_file(path, fmt=fmt)
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
    completed_sessions = sum(1 for s in sessions if s.completed)
    tot_repair_turns = sum(s.repair_turns for s in sessions)
    repair_sessions = sum(1 for s in sessions if s.repair_turns > 0)
    tot_zh_cues = sum(s.repair_cue_zh_turns for s in sessions)
    tot_en_cues = sum(s.repair_cue_en_turns for s in sessions)
    tot_post_abort = sum(s.post_abort_followups for s in sessions)
    tot_followup_user_turns = sum(max(0, s.user_turns - 1) for s in sessions)

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

    by_runtime = dict(sorted(collections.Counter(s.runtime for s in sessions).items()))

    return {
        "window": {
            "first_date": dates[0] if dates else "unknown",
            "last_date": dates[-1] if dates else "unknown",
            "since_filter": since,
            "min_turns": min_turns,
            "format": fmt,
        },
        "sessions": {
            "total": n,
            "by_runtime": by_runtime,
            "private_tmp": sum(1 for s in sessions if s.is_private_tmp),
            "private_tmp_share": round(sum(1 for s in sessions if s.is_private_tmp) / n, 4) if n else 0.0,
            "aborted": sum(1 for s in sessions if s.aborted),
            "abort_rate": round(sum(1 for s in sessions if s.aborted) / n, 4) if n else 0.0,
            "premature_end": sum(1 for s in sessions if s.premature_end),
            "premature_end_rate": round(sum(1 for s in sessions if s.premature_end) / n, 4) if n else 0.0,
            "completed": completed_sessions,
            "completion_rate": round(completed_sessions / n, 4) if n else 0.0,
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
            "prompt_tokens_per_completed_session": round(tot_prompt_tokens / completed_sessions, 1) if completed_sessions else 0.0,
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
        "friction": {
            "calibration_status": "uncalibrated_heuristic",
            "repair_turns_total": tot_repair_turns,
            "followup_user_turns": tot_followup_user_turns,
            "repair_turn_rate": round(tot_repair_turns / tot_followup_user_turns, 4) if tot_followup_user_turns else 0.0,
            "repair_sessions": repair_sessions,
            "repair_session_rate": round(repair_sessions / n, 4) if n else 0.0,
            "repair_turns_per_completed_session": round(tot_repair_turns / completed_sessions, 4) if completed_sessions else 0.0,
            "zh_cue_turns": tot_zh_cues,
            "en_cue_turns": tot_en_cues,
            "post_abort_followups": tot_post_abort,
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
    fr = report["friction"]
    st = report["stratification"]

    runtimes_str = ", ".join(f"{k}={v}" for k, v in s.get("by_runtime", {}).items()) or "none"

    lines = [
        "## Trace Telemetry Summary",
        "",
        f"- **Window:** `{w['first_date']}` to `{w['last_date']}` (`min_turns={w['min_turns']}`, `format={w.get('format', 'auto')}`)",
        f"- **Sessions analyzed:** `{s['total']}` (runtimes: `{runtimes_str}`; completed `{s['completed']}` / `{s['completion_rate']*100:.1f}%`; named project `{s['total'] - s['private_tmp']}`, `--private-tmp--` `{s['private_tmp']}` / `{s['private_tmp_share']*100:.1f}%`)",
        f"- **Assistant turns:** P50 `{s['turns_p50']}` / P90 `{s['turns_p90']}` / P99 `{s['turns_p99']}` (sessions > 5 MB: `{s['large_over_5mb']}`)",
        f"- **Context byte share (pooled):** tool outputs `{c['tool_result_char_share_pooled']*100:.1f}%`, assistant `{c['assistant_char_share']*100:.1f}%`, user `{c['user_char_share']*100:.1f}%` (per-session tool share `{c['tool_result_char_share_session_mean']*100:.1f}%`, 95% CI `[{c['tool_result_char_share_ci95'][0]*100:.1f}%, {c['tool_result_char_share_ci95'][1]*100:.1f}%]`)",
        f"- **Prompt cache hit rate (pooled):** `{t['pooled_cache_hit_rate']*100:.2f}%` across `{t['total_prompt_tokens']:,}` prompt tokens (`{t['prompt_tokens_per_completed_session']:,.1f}` prompt tokens / completed session; per-session mean `{t['session_cache_hit_mean']*100:.1f}%`, 95% CI `[{t['session_cache_hit_ci95'][0]*100:.1f}%, {t['session_cache_hit_ci95'][1]*100:.1f}%]`)",
        f"- **Tool surface:** `{tl['total_calls']:,}` calls, `{tl['total_errors']:,}` errors (`{tl['pooled_error_rate']*100:.2f}%` pooled)",
        f"- **Human–agent friction (`{fr['calibration_status']}`):** `{fr['repair_turns_total']}` repair turns across `{fr['repair_sessions']}` sessions (`{fr['repair_turns_per_completed_session']:.2f}` / completed session; ZH cues `{fr['zh_cue_turns']}`, EN cues `{fr['en_cue_turns']}`, post-abort `{fr['post_abort_followups']}`)",
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
    parser.add_argument(
        "--format",
        choices=("auto", "omp", "claude", "codex"),
        default="auto",
        help="trace schema adapter (default: auto-detect per file)",
    )
    parser.add_argument("--markdown", action="store_true", help="render Markdown report instead of JSON")
    args = parser.parse_args()

    if not args.sessions_dir.exists():
        print(f"error: sessions_dir not found: {args.sessions_dir}", file=sys.stderr)
        return 1

    report = analyze_directory(
        args.sessions_dir, since=args.since, min_turns=args.min_turns, seed=args.seed, fmt=args.format
    )
    if args.markdown:
        print(render_markdown(report))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
