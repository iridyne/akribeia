#!/usr/bin/env python3
"""N-of-1 single-case autocorrelation & power simulator for Akribeia.

Quantifies why naive before/after (AB) comparisons inflate false positives when
single-developer daily/session harness metrics exhibit AR(1) serial dependence,
and compares AB vs ABAB vs randomized alternating permutation designs.

Addresses Open Question #4 in docs/prior-art.md. Standard library only.

Usage:
    python3 scripts/nof1_power.py --seed 42 --trials 800 --markdown
"""

from __future__ import annotations

import argparse
import json
import math
import random
from typing import Any


def _ar1_noise(n: int, rho: float, rng: random.Random) -> list[float]:
    """Generate unit-variance zero-mean AR(1) series: x_t = rho * x_{t-1} + eps_t."""
    sigma_eps = math.sqrt(max(1e-12, 1.0 - rho * rho))
    series = [rng.gauss(0.0, 1.0)]
    for _ in range(1, n):
        series.append(rho * series[-1] + rng.gauss(0.0, sigma_eps))
    return series


def _schedule(design: str, n: int, rng: random.Random) -> list[int]:
    """Return binary treatment assignment (0=control, 1=treatment) of length n."""
    if design == "before_after":
        half = n // 2
        return [0] * half + [1] * (n - half)
    if design == "abab":
        q = max(1, n // 4)
        out: list[int] = []
        arm = 0
        while len(out) < n:
            out.extend([arm] * q)
            arm = 1 - arm
        return out[:n]
    if design == "rand_alt":
        # Balanced randomized alternating pairs (prevents long runs, preserves 50/50 split)
        out = []
        for _ in range(n // 2):
            pair = [0, 1] if rng.random() < 0.5 else [1, 0]
            out.extend(pair)
        if len(out) < n:
            out.append(rng.choice([0, 1]))
        return out
    raise ValueError(f"unknown design: {design}")


def _welch_z_significant(values: list[float], arms: list[int], alpha: float = 0.05) -> bool:
    """Two-sided normal-approx difference-in-means test (naive i.i.d. assumption)."""
    a = [v for v, g in zip(values, arms) if g == 0]
    b = [v for v, g in zip(values, arms) if g == 1]
    if len(a) < 2 or len(b) < 2:
        return False
    ma = sum(a) / len(a)
    mb = sum(b) / len(b)
    va = sum((x - ma) ** 2 for x in a) / (len(a) - 1)
    vb = sum((x - mb) ** 2 for x in b) / (len(b) - 1)
    se = math.sqrt(va / len(a) + vb / len(b))
    if se <= 1e-12:
        return False
    z = abs(mb - ma) / se
    # Normal two-sided critical value for alpha=0.05
    z_crit = 1.959963984540054 if abs(alpha - 0.05) < 1e-9 else 1.959963984540054
    return z >= z_crit


def _pair_randomization_significant(
    values: list[float], arms: list[int], rng: random.Random, *, perms: int = 200, alpha: float = 0.05
) -> bool:
    """Exact-structure paired sign-flip randomization test for balanced alternating pairs."""
    diffs: list[float] = []
    for i in range(0, len(values) - 1, 2):
        # treatment minus control inside each randomized pair
        if arms[i] == 1 and arms[i + 1] == 0:
            diffs.append(values[i] - values[i + 1])
        elif arms[i] == 0 and arms[i + 1] == 1:
            diffs.append(values[i + 1] - values[i])
    if not diffs:
        return False
    obs = abs(sum(diffs) / len(diffs))
    extreme = 0
    for _ in range(perms):
        perm_mean = abs(sum(d if rng.random() < 0.5 else -d for d in diffs) / len(diffs))
        if perm_mean >= obs - 1e-12:
            extreme += 1
    p_val = (extreme + 1) / (perms + 1)
    return p_val <= alpha


def run_simulation(
    *,
    rhos: tuple[float, ...] = (0.0, 0.3, 0.5, 0.7),
    sample_sizes: tuple[int, ...] = (20, 40, 80),
    effect_sd: float = 0.5,
    trials: int = 600,
    seed: int = 42,
) -> dict[str, Any]:
    """Run Monte Carlo grid for null Type I error and alternative power."""
    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []
    designs = ("before_after", "abab", "rand_alt_perm")

    for n in sample_sizes:
        for rho in rhos:
            for design in designs:
                fp = 0
                tp = 0
                for _ in range(trials):
                    sched_kind = "rand_alt" if design == "rand_alt_perm" else design
                    arms = _schedule(sched_kind, n, rng)
                    noise_null = _ar1_noise(n, rho, rng)
                    noise_alt = _ar1_noise(n, rho, rng)
                    alt_vals = [x + (effect_sd if g == 1 else 0.0) for x, g in zip(noise_alt, arms)]

                    if design == "rand_alt_perm":
                        if _pair_randomization_significant(noise_null, arms, rng):
                            fp += 1
                        if _pair_randomization_significant(alt_vals, arms, rng):
                            tp += 1
                    else:
                        if _welch_z_significant(noise_null, arms):
                            fp += 1
                        if _welch_z_significant(alt_vals, arms):
                            tp += 1

                rows.append(
                    {
                        "n": n,
                        "rho": rho,
                        "design": design,
                        "type1_fp_rate": round(fp / trials, 4),
                        "power": round(tp / trials, 4),
                    }
                )

    return {
        "seed": seed,
        "trials": trials,
        "alpha": 0.05,
        "effect_sd": effect_sd,
        "rows": rows,
    }


def render_markdown(res: dict[str, Any]) -> str:
    lines = [
        f"## N-of-1 Autocorrelation & Power Simulation (`seed={res['seed']}`, `trials={res['trials']}`, `effect={res['effect_sd']} SD`, `alpha={res['alpha']}`)",
        "",
        "| Sessions (N) | AR(1) rho | Before/After FP | ABAB FP | Rand-Alt Perm FP | Before/After Power | ABAB Power | Rand-Alt Perm Power |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    grouped: dict[tuple[int, float], dict[str, dict[str, Any]]] = {}
    for row in res["rows"]:
        grouped.setdefault((row["n"], row["rho"]), {})[row["design"]] = row
    for (n, rho), d in sorted(grouped.items()):
        ba = d["before_after"]
        ab = d["abab"]
        ra = d["rand_alt_perm"]
        lines.append(
            f"| {n} | {rho:.1f} | {ba['type1_fp_rate']*100:.1f}% | {ab['type1_fp_rate']*100:.1f}% | "
            f"{ra['type1_fp_rate']*100:.1f}% | {ba['power']*100:.1f}% | {ab['power']*100:.1f}% | {ra['power']*100:.1f}% |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--trials", type=int, default=600)
    parser.add_argument("--effect-sd", type=float, default=0.5)
    parser.add_argument("--markdown", action="store_true")
    args = parser.parse_args()

    res = run_simulation(trials=args.trials, effect_sd=args.effect_sd, seed=args.seed)
    if args.markdown:
        print(render_markdown(res))
    else:
        print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
