# Quantitative Study: N-of-1 Autocorrelation & Power for Single-User Harness Evaluation

> **Status:** Complete simulation study (`EXP-0016`, addressing Open Question #4 in `docs/prior-art.md`).  
> **Reproduce verbatim:** `python3 scripts/nof1_power.py --seed 42 --trials 1000 --markdown`

## 1. Motivation

A single-developer harness playground has no parallel control group (`docs/playground.md`). Consecutive coding sessions share the same codebase, sprint phase, and task difficulty, introducing positive AR(1) serial autocorrelation ($\rho > 0$) into daily and session metrics. Applying a standard before/after (`AB`) two-sample test assumes independent observations and severely underestimates variance under serial dependence.

## 2. Simulation Protocol

- **Data-generating process:** Unit-variance AR(1) series $x_t = \rho x_{t-1} + \sqrt{1 - \rho^2}\,\varepsilon_t$, $\varepsilon_t \sim \mathcal{N}(0, 1)$, evaluated at $\rho \in \{0.0, 0.3, 0.5, 0.7\}$ and total sessions $N \in \{20, 40, 80\}$.
- **Null vs. alternative:** Null $\Delta = 0$ measures empirical Type I false-positive rate (nominal $\alpha = 0.05$); alternative $\Delta = 0.5\,\text{SD}$ measures statistical power (`1,000` Monte Carlo trials per cell, fixed `seed=42`).
- **Designs compared:**
  1. **Before/After (`AB`)** with naive Welch two-sample z-test;
  2. **Reversal (`ABAB`)** with naive Welch two-sample z-test;
  3. **Randomized Alternating Pairs (`Rand-Alt Perm`)** — consecutive sessions are randomly ordered `(0, 1)` or `(1, 0)` and evaluated with a paired sign-flip randomization test (`200` permutations per trial).

## 3. Measured Results (`seed=42`, `trials=1000`, `effect=0.5 SD`, `alpha=0.05`)

| Sessions (N) | AR(1) $\rho$ | Before/After FP | ABAB FP | Rand-Alt Perm FP | Before/After Power | ABAB Power | Rand-Alt Perm Power |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 0.0 | 7.0% | 6.8% | **4.2%** | 21.9% | 22.7% | 16.0% |
| 20 | 0.3 | 17.8% | 17.2% | **5.4%** | 31.7% | 31.7% | 22.5% |
| 20 | 0.5 | 27.2% | 16.9% | **5.9%** | 40.1% | 31.9% | 28.7% |
| 20 | 0.7 | **42.2%** | 24.7% | **5.1%** | 50.4% | 35.8% | 41.3% |
| 40 | 0.0 | 5.0% | 4.8% | **5.9%** | 35.7% | 36.7% | 34.3% |
| 40 | 0.3 | 16.2% | 13.9% | **5.6%** | 40.6% | 40.7% | 43.4% |
| 40 | 0.5 | 28.4% | 25.0% | **4.9%** | 46.9% | 43.7% | **56.2%** |
| 40 | 0.7 | **41.6%** | 35.3% | **5.6%** | 54.2% | 50.2% | **78.3%** |
| 80 | 0.0 | 5.6% | 6.5% | **5.0%** | 61.3% | 62.4% | 60.0% |
| 80 | 0.3 | 17.0% | 16.0% | **3.3%** | 62.3% | 59.8% | **73.8%** |
| 80 | 0.5 | 25.6% | 25.8% | **5.4%** | 59.0% | 59.3% | **85.3%** |
| 80 | 0.7 | **43.0%** | 41.4% | **5.1%** | 61.1% | 58.7% | **97.2%** |

## 4. Operational Conclusions for Akribeia

1. **Naive Before/After fails catastrophically under serial dependence.** At $\rho = 0.7$, a null harness edit that does nothing is falsely declared "significant" **41.6%–43.0%** of the time (8× nominal $\alpha$). Even phase-reversal `ABAB` still inflates false positives to **24.7%–41.4%** if scored with an i.i.d. two-sample test.
2. **Randomized alternating pairs preserve nominal error AND gain power.** Because adjacent sessions share correlated task difficulty, within-pair differencing cancels serial drift: `Rand-Alt Perm` holds false positives at **3.3%–5.9%** across every $\rho$, while raising power at $N=40, \rho=0.7$ from **54.2% to 78.3%** (and **97.2%** at $N=80$).
3. **Minimum sample rule.** At $N=20$, even well-controlled alternating trials have only **16%–41%** power for a medium (`0.5 SD`) effect — confirming why `docs/playground.md` treats 20 sessions as a weak signal and requires `N >= 40` (or large effect sizes) for credible promotion.
