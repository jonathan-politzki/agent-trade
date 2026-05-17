"""Smoke tests for the curated-content S3 path. fast mode only, no LLM calls."""
from car_market.config import S3Config
from car_market.scenarios.s3_open_market import run


def test_s3_runs_with_curated_cars_and_sellers():
    cfg = S3Config(
        seed=0, reputation_gamma=0.5, mode="fast",
        cars_source="curated", sellers_source="curated",
        m_buyers=30, T=60,
    )
    s = run(cfg)
    assert s["listings_total"] == 200
    assert s["deals"] >= 0           # don't care about exact count


def test_s3_default_uses_curated_cars():
    cfg = S3Config(seed=0, reputation_gamma=0.5, mode="fast",
                    m_buyers=30, T=60)
    s = run(cfg)
    assert s["listings_total"] == 200   # all 200 curated cars get listed


def test_s3_can_still_use_generator_explicitly():
    cfg = S3Config(seed=0, reputation_gamma=0.5, mode="fast",
                    cars_source="generator", sellers_source="anonymous",
                    m_buyers=30, T=60)
    s = run(cfg)
    assert s["listings_total"] > 0
