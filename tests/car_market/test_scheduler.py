from car_market.scheduler import poisson_arrivals


def test_arrival_count_close_to_m():
    arrivals = poisson_arrivals(m=150, T=400, seed=0)
    assert 120 <= len(arrivals) <= 180


def test_arrival_times_sorted():
    arrivals = poisson_arrivals(m=150, T=400, seed=0)
    assert arrivals == sorted(arrivals)


def test_arrival_times_in_range():
    arrivals = poisson_arrivals(m=150, T=400, seed=0)
    assert all(0 <= t < 400 for t in arrivals)


def test_arrival_deterministic_per_seed():
    a = poisson_arrivals(m=100, T=200, seed=7)
    b = poisson_arrivals(m=100, T=200, seed=7)
    assert a == b


def test_arrival_count_zero_when_m_is_zero():
    arrivals = poisson_arrivals(m=0, T=100, seed=0)
    assert arrivals == []
