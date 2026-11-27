"""Zero-dependency unittest suite for Akribeia (stdlib only).

Run:
    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import akribeia  # noqa: E402
import analyze_traces  # noqa: E402
import audit  # noqa: E402
import nof1_power  # noqa: E402
import payload_gate  # noqa: E402
import report  # noqa: E402


class TestAuditAndReport(unittest.TestCase):
    def test_audit_selftest_passes(self) -> None:
        self.assertEqual(audit.selftest(), 0)

    def test_live_ledgers_pass_audit_and_secret_scan(self) -> None:
        ledgers = audit.load_ledgers()
        self.assertEqual(audit.check_ledgers(ledgers), [])
        self.assertEqual(audit.scan_secrets(), [])

    def test_report_renders_all_sections(self) -> None:
        md = report.render()
        for heading in (
            "# Ledger",
            "## Literature claims",
            "## Local hypotheses",
            "## Decisions",
            "## Changes",
            "## Experiments",
            "## Incidents",
        ):
            self.assertIn(heading, md)


class TestPayloadGate(unittest.TestCase):
    def setUp(self) -> None:
        import tomllib

        with (ROOT / "contracts" / "example-harness-contract.toml").open("rb") as h:
            self.contract = tomllib.load(h)

    def test_selftest_oracle_passes(self) -> None:
        self.assertEqual(payload_gate.selftest(), 0)

    def test_anthropic_and_openai_good_payloads_pass(self) -> None:
        for name in ("anthropic_good.json", "openai_good.json"):
            raw = json.loads((ROOT / "examples" / "demo-payloads" / name).read_text(encoding="utf-8"))
            norm = payload_gate.normalize_payload(raw)
            res = payload_gate.evaluate_contract(
                self.contract, norm, baseline_sha256=norm.system_prefix_sha256
            )
            self.assertTrue(res["ok"], f"{name} failed unexpectedly: {res}")
            self.assertEqual(res["passed_count"], res["total_count"])

    def test_cache_prefix_drift_detected(self) -> None:
        base_raw = json.loads(
            (ROOT / "examples" / "demo-payloads" / "anthropic_good.json").read_text(encoding="utf-8")
        )
        drift_raw = json.loads(
            (ROOT / "examples" / "demo-payloads" / "anthropic_broken_cache_drift.json").read_text(
                encoding="utf-8"
            )
        )
        base = payload_gate.normalize_payload(base_raw)
        drift = payload_gate.normalize_payload(drift_raw)
        res = payload_gate.evaluate_contract(
            self.contract, drift, baseline_sha256=base.system_prefix_sha256
        )
        self.assertFalse(res["ok"])
        self.assertFalse(res["cache_check"]["stable"])

    def test_vacuous_negative_contract_rejected_at_schema_stage(self) -> None:
        bad = {
            "assertion": [
                {
                    "id": "bad-neg",
                    "kind": "must_not_contain",
                    "scope": "any",
                    "pattern": "some-old-path",
                }
            ]
        }
        dummy = payload_gate.normalize_payload({"messages": [{"role": "user", "content": "hi"}]})
        res = payload_gate.evaluate_contract(bad, dummy)
        self.assertFalse(res["ok"])
        self.assertEqual(res["stage"], "contract_schema")
        self.assertTrue(any("INC-0006" in e for e in res["schema_errors"]))

    def test_negative_assertion_fails_when_witness_fails(self) -> None:
        # Simulate dead extension: both forbidden old string AND positive witness are absent.
        raw = {
            "system": [{"type": "text", "text": "Minimal fallback system prompt."}],
            "messages": [{"role": "user", "content": "ping"}],
            "tools": [{"name": "read"}],
        }
        res = payload_gate.evaluate_contract(self.contract, payload_gate.normalize_payload(raw))
        by_id = {r["id"]: r for r in res["results"]}
        self.assertFalse(res["ok"])
        self.assertFalse(by_id["rule-closure"]["passed"])
        self.assertFalse(by_id["no-legacy-placeholder"]["passed"])
        self.assertIn("blocked vacuous pass", by_id["no-legacy-placeholder"]["detail"])

    def test_startup_log_gate_fails_closed(self) -> None:
        raw = json.loads(
            (ROOT / "examples" / "demo-payloads" / "anthropic_good.json").read_text(encoding="utf-8")
        )
        res = payload_gate.evaluate_contract(
            self.contract,
            payload_gate.normalize_payload(raw),
            log_text="WARN starting\nERROR Failed to load extension repo-rules\n",
        )
        self.assertFalse(res["ok"])
        self.assertEqual(len(res["log_failures"]), 1)

    def test_mcp_bloat_fixture_rejected_by_tool_budget(self) -> None:
        raw = json.loads(
            (ROOT / "examples" / "demo-payloads" / "anthropic_mcp_bloat.json").read_text(encoding="utf-8")
        )
        res = payload_gate.evaluate_contract(self.contract, payload_gate.normalize_payload(raw))
        self.assertFalse(res["ok"])
        tb = res["tool_budget_check"]
        self.assertIsNotNone(tb)
        self.assertFalse(tb["ok"])
        self.assertEqual(tb["mcp_tools"], 30)
        self.assertEqual(tb["by_server"], {"chatops": 30})
        self.assertTrue(any("chatops" in v for v in tb["violations"]))

    def test_prompt_mounted_mcp_bloat_rejected(self) -> None:
        lines = [f"- mcp__chatops_tool_{i:02d}: synthetic mounted command" for i in range(1, 26)]
        raw = {
            "model": "example-model",
            "system": [
                {
                    "type": "text",
                    "text": (
                        "Never end a turn on raw tool output.\n"
                        "Use the sanctioned read escalation path instead of eval open().\n"
                        + "\n".join(lines)
                    ),
                }
            ],
            "messages": [{"role": "user", "content": "ping"}],
            "tools": [{"name": "read", "input_schema": {"type": "object"}}],
        }
        res = payload_gate.evaluate_contract(self.contract, payload_gate.normalize_payload(raw))
        self.assertFalse(res["ok"])
        tb = res["tool_budget_check"]
        self.assertFalse(tb["ok"])
        self.assertEqual(tb["by_server"].get("chatops"), 25)


class TestCli(unittest.TestCase):
    def test_help_lists_every_command(self) -> None:
        self.assertEqual(akribeia.main(["--help"]), 0)
        self.assertEqual(sorted(akribeia.COMMANDS), ["audit", "gate", "power", "report", "trace"])

    def test_unknown_command_exits_2(self) -> None:
        self.assertEqual(akribeia.main(["nope"]), 2)

    def test_dispatch_forwards_exit_code(self) -> None:
        original = sys.argv
        try:
            self.assertEqual(akribeia.main(["audit", "--selftest"]), 0)
        finally:
            sys.argv = original


class TestAnalyzeTraces(unittest.TestCase):
    def test_demo_sessions_analysis(self) -> None:
        rep = analyze_traces.analyze_directory(ROOT / "examples" / "demo-sessions", seed=42)
        self.assertEqual(rep["sessions"]["total"], 3)
        self.assertEqual(rep["sessions"]["private_tmp"], 1)
        self.assertEqual(rep["sessions"]["completed"], 3)
        self.assertEqual(rep["tools"]["total_calls"], 4)
        self.assertEqual(rep["tools"]["total_errors"], 1)
        # Single-digest sessions have higher cache hit rate than drifted session_002
        tc = rep["tokens_and_cache"]
        self.assertEqual(tc["single_digest_sessions"], 2)
        self.assertEqual(tc["multi_digest_sessions"], 1)
        self.assertGreater(tc["single_digest_cache_mean"], tc["multi_digest_cache_mean"])
        self.assertGreater(tc["prompt_tokens_per_completed_session"], 0)
        # R4 bilingual + post-abort repair-turn heuristic
        fr = rep["friction"]
        self.assertEqual(fr["calibration_status"], "uncalibrated_heuristic")
        self.assertEqual(fr["repair_turns_total"], 1)
        self.assertEqual(fr["repair_sessions"], 1)
        self.assertEqual(fr["zh_cue_turns"], 1)
        self.assertEqual(fr["post_abort_followups"], 1)
        md = analyze_traces.render_markdown(rep)
        self.assertIn("## Trace Telemetry Summary", md)
        self.assertIn("uncalibrated_heuristic", md)

    def test_claude_code_adapter_parses_real_schema(self) -> None:
        rep = analyze_traces.analyze_directory(ROOT / "examples" / "demo-sessions-cc", seed=42)
        self.assertEqual(rep["sessions"]["total"], 1)
        self.assertEqual(rep["sessions"]["by_runtime"], {"claude_code": 1})
        self.assertEqual(rep["sessions"]["completed"], 1)
        self.assertEqual(rep["tools"]["total_calls"], 2)
        self.assertEqual(rep["tools"]["total_errors"], 1)
        by_tool = {row["tool"]: row for row in rep["tools"]["by_tool"]}
        self.assertEqual(by_tool["Bash"]["errors"], 1)
        self.assertEqual(by_tool["Read"]["errors"], 0)
        self.assertEqual(rep["friction"]["en_cue_turns"], 1)
        self.assertGreater(rep["tokens_and_cache"]["total_prompt_tokens"], 0)

    def test_codex_adapter_parses_real_schema_without_double_counting(self) -> None:
        rep = analyze_traces.analyze_directory(ROOT / "examples" / "demo-sessions-codex", seed=42)
        self.assertEqual(rep["sessions"]["total"], 1)
        self.assertEqual(rep["sessions"]["by_runtime"], {"codex": 1})
        self.assertEqual(rep["sessions"]["completed"], 1)
        self.assertEqual(rep["tools"]["total_calls"], 2)
        self.assertEqual(rep["tools"]["total_errors"], 1)
        by_tool = {row["tool"]: row for row in rep["tools"]["by_tool"]}
        self.assertEqual(by_tool["exec_command"]["errors"], 1)
        self.assertEqual(by_tool["read_file"]["errors"], 0)
        # Sum of last_token_usage across two steps = 2000 + 2500 = 4500 (not 2000 + 4500 cumulative)
        self.assertEqual(rep["tokens_and_cache"]["total_prompt_tokens"], 4500)

    def test_repair_calibration_metrics(self) -> None:
        preds = [True] * 10 + [False] * 10
        labels = [True] * 9 + [False] + [False] * 9 + [True]
        cal = analyze_traces.evaluate_repair_calibration(preds, labels)
        self.assertEqual(cal["n"], 20)
        self.assertAlmostEqual(cal["agreement"], 0.9)
        self.assertAlmostEqual(cal["cohen_kappa"], 0.8)
        self.assertTrue(cal["calibrated"])
        # Under-sampled (<20) must never report calibrated=True
        small = analyze_traces.evaluate_repair_calibration([True, False], [True, False])
        self.assertFalse(small["calibrated"])


class TestNof1Power(unittest.TestCase):
    def test_deterministic_and_autocorrelation_inflates_before_after_fp(self) -> None:
        r1 = nof1_power.run_simulation(rhos=(0.0, 0.7), sample_sizes=(40,), trials=150, seed=42)
        r2 = nof1_power.run_simulation(rhos=(0.0, 0.7), sample_sizes=(40,), trials=150, seed=42)
        self.assertEqual(r1, r2)
        by_key = {(row["rho"], row["design"]): row for row in r1["rows"]}
        # Under strong serial dependence (rho=0.7), naive before/after inflates FP well above 5%
        self.assertGreater(by_key[(0.7, "before_after")]["type1_fp_rate"], 0.25)
        # Randomized alternating permutation test stays controlled near nominal alpha=0.05
        self.assertLess(by_key[(0.7, "rand_alt_perm")]["type1_fp_rate"], 0.12)


if __name__ == "__main__":
    unittest.main()
