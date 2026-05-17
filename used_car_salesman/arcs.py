"""Multi-trade arcs: one seller, K sequential sales, reputation accumulates.

An *arc* answers the trust question that a single session cannot: if the slimy
salesman keeps doing the slimy thing, does it catch up with them? With
`reputation_visible=True` each successive buyer reads the cumulative review
ledger before they engage; with `reputation_visible=False` the same arc runs
with the reputation block stripped from the buyer's prompt (control).
"""
from __future__ import annotations

import json
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from itertools import product
from pathlib import Path

from .car import Car, load_fleet
from .config import SessionConfig, SWEEPS_DIR
from .personas import load_persona_by_id
from .reputation import Reputation, Review
from .session import run_session


@dataclass
class ArcConfig:
    arc_id: str
    seller_persona_id: str
    buyer_persona_id: str
    seller_model: str
    buyer_model: str
    car_ids: list[str]                # sequence of cars to sell, in order
    reputation_visible: bool
    seed: int
    max_turns: int = 22
    inspection_cost: float = 150.0


def _run_one_arc(arc: ArcConfig, fleet: dict[str, Car], sweep_dir: Path) -> dict:
    """Execute one arc sequentially. Returns a dict summary of the arc."""
    arc_dir = sweep_dir / arc.arc_id
    arc_dir.mkdir(parents=True, exist_ok=True)

    seller = load_persona_by_id(arc.seller_persona_id, "seller")
    buyer = load_persona_by_id(arc.buyer_persona_id, "buyer")
    reputation = Reputation(
        seller_id=arc.arc_id,
        seller_persona_id=arc.seller_persona_id,
        seller_model=arc.seller_model,
    )

    trades: list[dict] = []
    for i, car_id in enumerate(arc.car_ids):
        car = fleet[car_id]
        # Build a per-trade SessionConfig.
        cfg = SessionConfig(
            car_id=car_id,
            seller_persona_id=arc.seller_persona_id,
            buyer_persona_id=arc.buyer_persona_id,
            seller_model=arc.seller_model,
            buyer_model=arc.buyer_model,
            seller_knows_buyer=False,
            buyer_options_narrowed=True,
            hacking_tactic=None,
            max_turns=arc.max_turns,
            inspection_cost=arc.inspection_cost,
            seed=arc.seed * 100 + i,   # unique-ish per trade for dir naming
        )

        # Inject reputation only if treatment is on.
        rep_in = reputation if arc.reputation_visible else None
        result = run_session(None, car, seller, buyer, cfg, arc_dir,
                             reputation=rep_in, collect_review=True)

        # If a review came back, attach trade_index and add to reputation.
        if result.review is not None:
            result.review.trade_index = i
            result.review.transaction_id = result.session_id
            reputation.reviews.append(result.review)

        trade_row = result.to_row()
        trade_row["arc_id"] = arc.arc_id
        trade_row["trade_index"] = i
        trade_row["reputation_visible"] = arc.reputation_visible
        trade_row["seller_arc_n_sales"] = len(reputation.reviews)
        trade_row["seller_arc_mean_rating"] = reputation.mean_rating
        trades.append(trade_row)

    reputation.save(arc_dir / "reputation.json")
    (arc_dir / "arc_summary.json").write_text(json.dumps({
        "arc_id": arc.arc_id,
        "config": asdict(arc),
        "trades": trades,
    }, indent=2, default=str))
    return {"arc_id": arc.arc_id, "trades": trades, "reputation": reputation.to_json()}


def run_arcs(
    sweep_id: str,
    fleet_path: Path,
    arcs: list[ArcConfig],
    out_root: Path = SWEEPS_DIR,
    *,
    workers: int = 4,
) -> Path:
    sweep_dir = out_root / sweep_id
    sweep_dir.mkdir(parents=True, exist_ok=True)
    fleet = load_fleet(fleet_path)
    trades_path = sweep_dir / "trades.jsonl"
    trades_path.write_text("")

    (sweep_dir / "sweep_config.json").write_text(json.dumps({
        "sweep_id": sweep_id,
        "fleet_path": str(fleet_path),
        "n_arcs": len(arcs),
        "trades_per_arc": [len(a.car_ids) for a in arcs],
        "workers": workers,
        "arcs": [asdict(a) for a in arcs],
    }, indent=2))

    write_lock = threading.Lock()

    def emit_arc(arc_summary: dict) -> None:
        with write_lock:
            with trades_path.open("a") as f:
                for trade in arc_summary["trades"]:
                    f.write(json.dumps(trade, default=str) + "\n")

    print(f"\n=== arc sweep {sweep_id}: {len(arcs)} arcs, {workers} workers ===")
    print(f"     trades/arc = {[len(a.car_ids) for a in arcs[:3]]}...")

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_run_one_arc, a, fleet, sweep_dir): a for a in arcs}
        done = 0
        for fut in as_completed(futures):
            arc = futures[fut]
            try:
                summary = fut.result()
                emit_arc(summary)
                done += 1
                rep_n = len(summary["reputation"]["reviews"])
                rating = summary["reputation"]["mean_rating"]
                rating_str = f"{rating:.2f}/5" if rating is not None else "—"
                print(f"[{done:>3}/{len(arcs)}] arc {arc.arc_id} done — {rep_n} reviews, "
                      f"final rating {rating_str}, rep_visible={arc.reputation_visible}")
            except Exception as e:
                print(f"[??/??] ERROR on arc {arc.arc_id}: {type(e).__name__}: {e}")
    print(f"\nArc sweep complete. Trade rows at {trades_path}")
    return trades_path


def build_default_arcs(
    fleet_car_ids: list[str],
    *,
    seller_persona: str = "slimy",
    buyer_persona: str = "casual",
    seller_model: str = "gemini-2.5-flash-lite",
    buyer_models: list[str] | None = None,
    n_arcs_per_cell: int = 5,
    cars_per_arc: int = 8,
    base_seed: int = 1000,
) -> list[ArcConfig]:
    """Default sweep design for the trust experiment.

    Treatment x buyer_model x seed. Each arc selects a different car order
    (via per-arc shuffle keyed by seed).
    """
    buyer_models = buyer_models or ["gemini-2.5-flash"]
    arcs: list[ArcConfig] = []
    for treatment, buyer_model, i in product([True, False], buyer_models, range(n_arcs_per_cell)):
        rng = random.Random(base_seed + i * 37)
        cars = fleet_car_ids[:]
        rng.shuffle(cars)
        car_seq = cars[:cars_per_arc]
        tag = "rep" if treatment else "ctrl"
        arc_id = f"arc_{tag}_{buyer_model.replace('-','_')}_s{i:02d}"
        arcs.append(ArcConfig(
            arc_id=arc_id,
            seller_persona_id=seller_persona,
            buyer_persona_id=buyer_persona,
            seller_model=seller_model,
            buyer_model=buyer_model,
            car_ids=car_seq,
            reputation_visible=treatment,
            seed=base_seed + i,
        ))
    return arcs
