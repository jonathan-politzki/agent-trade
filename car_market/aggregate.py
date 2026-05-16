"""Aggregate fast-mode runs across seeds and reputation_gamma values to
produce the headline welfare-delta chart."""
from __future__ import annotations

import random
from pathlib import Path

from .config import S3Config
from .scenarios.s3_open_market import run as run_s3


def sweep(seeds: list[int], gammas: list[float], out_dir: str = "runs") -> dict:
    rows = []
    for seed in seeds:
        for gamma in gammas:
            cfg = S3Config(seed=seed, reputation_gamma=gamma, out_dir=out_dir)
            r = run_s3(cfg)
            label = "visible" if gamma > 0 else "hidden"
            rows.append({**r, "gamma_label": label})
    return {"rows": rows}


def bootstrap_ci(values: list[float], n_boot: int = 1000, alpha: float = 0.05,
                  seed: int = 0) -> tuple[float, float, float]:
    """Return (mean, lo, hi) where (lo, hi) is the 95% bootstrap CI of the mean."""
    rng = random.Random(seed)
    n = len(values)
    if n == 0:
        return 0.0, 0.0, 0.0
    means = []
    for _ in range(n_boot):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    return (
        sum(values) / n,
        means[int(alpha / 2 * n_boot)],
        means[int((1 - alpha / 2) * n_boot)],
    )


def welfare_delta_report(sweep_rows: list[dict]) -> dict:
    by_gamma: dict[str, list[float]] = {"visible": [], "hidden": []}
    for r in sweep_rows:
        by_gamma[r["gamma_label"]].append(r.get("total_welfare", 0.0))
    visible_mean, vlo, vhi = bootstrap_ci(by_gamma["visible"])
    hidden_mean, hlo, hhi = bootstrap_ci(by_gamma["hidden"])
    return {
        "visible_mean": visible_mean, "visible_ci": [vlo, vhi],
        "hidden_mean": hidden_mean, "hidden_ci": [hlo, hhi],
        "delta": visible_mean - hidden_mean,
        "n_seeds_visible": len(by_gamma["visible"]),
        "n_seeds_hidden": len(by_gamma["hidden"]),
    }
