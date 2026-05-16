from car_market.evaluator import deal_welfare, run_metrics, gini


def test_deal_welfare_components():
    bs, ss, dw = deal_welfare(price=16000.0, true_value=15000.0,
                                 buyer_utility=17500.0)
    assert bs == 1500.0
    assert ss == 1000.0
    assert dw == 2500.0


def test_run_metrics_empty():
    m = run_metrics(deals=[], no_deal_buyers=10)
    assert m["total_welfare"] == 0.0
    assert m["pct_buyers_served"] == 0.0
    assert m["n_deals"] == 0


def test_gini_zero_for_all_equal():
    assert abs(gini([5.0, 5.0, 5.0, 5.0])) < 1e-9


def test_gini_handles_empty():
    assert gini([]) == 0.0


def test_gini_handles_zero_sum():
    assert gini([0.0, 0.0, 0.0]) == 0.0


def test_run_metrics_with_deals():
    deals = [
        {"buyer": "B_01", "buyer_surplus": 100.0, "seller_surplus": 50.0, "deal_welfare": 150.0},
        {"buyer": "B_02", "buyer_surplus": 200.0, "seller_surplus": 100.0, "deal_welfare": 300.0},
    ]
    m = run_metrics(deals=deals, no_deal_buyers=2)
    assert m["n_deals"] == 2
    assert m["total_welfare"] == 450.0
    # mean buyer surplus over all 4 buyers (2 deals + 2 no-deal): (100+200+0+0)/4 = 75
    assert m["mean_buyer_surplus"] == 75.0
    # mean seller surplus over only the 2 closed deals: (50+100)/2 = 75
    assert m["mean_seller_surplus"] == 75.0
    # pct buyers served: 2/4 = 0.5
    assert m["pct_buyers_served"] == 0.5
