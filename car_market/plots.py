"""Matplotlib plotting for car-market figures."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def welfare_delta_bar(report: dict, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6, 4))
    means = [report["hidden_mean"], report["visible_mean"]]
    errs_lo = [
        report["hidden_mean"] - report["hidden_ci"][0],
        report["visible_mean"] - report["visible_ci"][0],
    ]
    errs_hi = [
        report["hidden_ci"][1] - report["hidden_mean"],
        report["visible_ci"][1] - report["visible_mean"],
    ]
    ax.bar(["hidden", "visible"], means,
            yerr=[errs_lo, errs_hi],
            color=["#aaa", "#3a7"],
            capsize=8)
    ax.set_ylabel("Total welfare ($)")
    ax.set_title(f"Reputation institution welfare delta = ${report['delta']:.0f}")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
