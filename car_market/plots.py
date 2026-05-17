"""Matplotlib plotting for car-market figures."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def s1_heatmap(json_path: Path, out_path: Path) -> None:
    import json
    import numpy as np
    d = json.loads(Path(json_path).read_text())
    surplus = np.array(d["surplus"])
    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(surplus, cmap="RdYlGn", aspect="auto")
    ax.set_xticks(range(len(d["sellers"])))
    ax.set_xticklabels(d["sellers"], rotation=45)
    ax.set_yticks(range(len(d["personas"])))
    ax.set_yticklabels(d["personas"])
    fig.colorbar(im, ax=ax, label="Seller surplus over true_value ($)")
    ax.set_title("S1: per-seller surplus across personas\n(H=honest, M=moderate, A=aggressive)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def s2_curve(rows_path: Path, out_path: Path) -> None:
    import json
    from collections import defaultdict
    rows = json.loads(Path(rows_path).read_text())
    by_m: dict[int, list[float]] = defaultdict(list)
    by_m_full: dict[int, list[float]] = defaultdict(list)
    by_m_first: dict[int, list[float]] = defaultdict(list)
    for r in rows:
        by_m[r["m"]].append(r["regret"])
        by_m_full[r["m"]].append(r["full_search_U"])
        by_m_first[r["m"]].append(r["first_acceptable_U"])
    ms = sorted(by_m)
    regret_means = [sum(by_m[m]) / len(by_m[m]) for m in ms]
    full_means = [sum(by_m_full[m]) / len(by_m_full[m]) for m in ms]
    first_means = [sum(by_m_first[m]) / len(by_m_first[m]) for m in ms]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    axes[0].plot(ms, full_means, marker="o", label="full_search", color="#3a7")
    axes[0].plot(ms, first_means, marker="s", label="first_acceptable", color="#aaa")
    axes[0].set_xlabel("Pool size m")
    axes[0].set_ylabel("Mean utility ($)")
    axes[0].set_title("S2: utility under two buyer policies")
    axes[0].legend()
    axes[1].plot(ms, regret_means, marker="o", color="#c33")
    axes[1].set_xlabel("Pool size m")
    axes[1].set_ylabel("Mean regret (full - first_acceptable, $)")
    axes[1].set_title("S2: paradox of choice — regret rises with m")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


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
