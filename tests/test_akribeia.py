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
        self.assertEqual(rep["sessions"]["total"], 2)
        self.assertEqual(rep["sessions"]["private_tmp"], 1)
        self.assertEqual(rep["tools"]["total_calls"], 3)
        self.assertEqual(rep["tools"]["total_errors"], 1)
        # Single-digest session_001 has higher cache hit rate than drifted session_002
        tc = rep["tokens_and_cache"]
        self.assertEqual(tc["single_digest_sessions"], 1)
        self.assertEqual(tc["multi_digest_sessions"], 1)
        self.assertGreater(tc["single_digest_cache_mean"], tc["multi_digest_cache_mean"])
        md = analyze_traces.render_markdown(rep)
        self.assertIn("## Trace Telemetry Summary", md)


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
