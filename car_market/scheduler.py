"""Poisson arrival scheduler for S3 open market."""
from __future__ import annotations

import random


def poisson_arrivals(m: int, T: int, seed: int) -> list[int]:
    """Sample arrival times for `m` expected buyers over `T` time steps.
    Each step independently has probability λ=m/T of a buyer arriving.
    Returns sorted list of integer step indices. Deterministic given seed.

    Length of result is Poisson(m), not exactly m — that's the point of the
    arrival process. m is the *expected* count."""
    rng = random.Random(seed)
    if T <= 0 or m <= 0:
        return []
    lam = m / T
    arrivals: list[int] = []
    for t in range(T):
        if rng.random() < lam:
            arrivals.append(t)
    return arrivals
