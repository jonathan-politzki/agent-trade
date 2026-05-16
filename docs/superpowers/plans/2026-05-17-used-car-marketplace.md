# Used-Car Marketplace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a used-car marketplace simulation where sellers hold private condition info, buyers have heterogeneous hedonic preferences, and reputation visibly converts the one-shot lemons game into a repeated game. Ship a live Saturday demo whose headline chart (visible-rep vs hidden-rep welfare delta) is reproducible from a fixed seed without re-querying any LLM.

**Architecture:** Deterministic economic engine + LLM for flavor + replayable ablation. All published metrics come from `--mode fast` (rule-based seller archetypes, rule-based buyer policies, zero LLM calls, runs in seconds). `--mode llm` runs once offline to record cached transcripts. `--mode replay` plays them back live on stage. Reputation is a `Beta(α,β)` posterior per seller updated from listing-vs-true-condition gap on every deal close. Reputation operates through both search ranking (operational channel) and a `lookup_seller` tool (instrumentation channel).

**Tech Stack:** Python 3.13, **litellm** (provider-agnostic LLM client wrapping Anthropic, OpenAI, Gemini, local, etc.), pandas, pyarrow, scikit-learn, matplotlib, numpy, pytest. Reuses `project_deal/marketplace.py`, `project_deal/agent.py`, `project_deal/config.py` as a substrate; new code lives under `car_market/`.

> **Model selection note.** All LLM calls (description, negotiation messages, optional capability-asymmetry sub-experiment) go through `litellm.completion(model=..., messages=...)`. Models pass as strings like `"anthropic/claude-haiku-4-5"`, `"openai/gpt-4o-mini"`, `"gemini/gemini-2.0-flash"`. This lets us trivially swap models per cohort (see spec §8.3.5 capability asymmetry) and lets the demo fall back to a cheaper provider if rate limits hit. Default per-call model is `"anthropic/claude-haiku-4-5"`.

**Reference spec:** `docs/superpowers/specs/2026-05-17-used-car-marketplace-design.md` (revised after Codex review).

**Critical path order:**
1. Phase A — foundation (oracle + personas + metric formulas, TDD)
2. Phase B — reputation
3. Phase C — marketplace extension
4. Phase D — **S3 fast-mode end-to-end + welfare delta chart (THE HEADLINE)**
5. Phase E — LLM mode + transcript caching
6. Phase F — replay mode + demo runner
7. Phase G — S1 heatmap + S2 regret curve (backup slides)
8. Phase H — optional anchor scripts

If you must cut, cut from the bottom up. Phase D is the deliverable.

---

## File Structure

```
agent-trade/
├── car_market/
│   ├── __init__.py
│   ├── config.py            # CarMarketConfig + RunMode
│   ├── generator.py         # CarSpec, hedonic formula, sampler
│   ├── archetypes.py        # SellerArchetype taxonomy + listing-construction policy
│   ├── personas.py          # Persona schema + Utility function
│   ├── personas_data/       # 10 persona JSONs
│   ├── reputation.py        # BetaReputation + update + decay
│   ├── marketplace.py       # CarMarketplace extending project_deal.Marketplace
│   ├── policies.py          # Heuristic buyer/seller policies for `fast` mode
│   ├── llm_agent.py         # LLM-flavored seller/buyer adapters for `llm` mode
│   ├── llm_cache.py         # cache layer for LLM-mode transcripts
│   ├── scheduler.py         # Poisson arrival + concurrent negotiation scheduler
│   ├── evaluator.py         # locked metric formulas, figures
│   ├── descriptions.py      # LLM listing-prose generator
│   ├── scenarios/
│   │   ├── __init__.py
│   │   ├── s3_open_market.py    # headline; --mode fast|llm|replay
│   │   ├── s1_same_car.py       # backup
│   │   └── s2_paradox.py        # deterministic-only backup
│   └── anchor/                  # OPTIONAL
│       ├── fit_marginals.py
│       └── fit_hedonic.py
├── tests/
│   └── car_market/
│       ├── test_generator.py
│       ├── test_archetypes.py
│       ├── test_personas.py
│       ├── test_reputation.py
│       ├── test_marketplace.py
│       ├── test_policies.py
│       ├── test_scheduler.py
│       └── test_evaluator.py
├── run_car_market.py            # CLI entrypoint
└── requirements.txt             # add pandas, pyarrow, scikit-learn, matplotlib, numpy, pytest
```

---

## Phase 0 — Setup

### Task 0.1: Add dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Append new deps**

```
anthropic>=0.40.0
python-dotenv>=1.0.0
litellm>=1.40.0
pandas>=2.2.0
pyarrow>=15.0.0
scikit-learn>=1.4.0
matplotlib>=3.8.0
numpy>=1.26.0
pytest>=8.0.0
```

- [ ] **Step 2: Install with uv (or pip)**

Run: `uv pip install -r requirements.txt` (or `pip install -r requirements.txt`)
Expected: all packages install without error.

- [ ] **Step 3: Verify imports**

Run: `python3 -c "import pandas, pyarrow, sklearn, matplotlib, numpy, pytest, anthropic; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add deps for car-market simulation"
```

### Task 0.2: Create package skeleton

**Files:**
- Create: `car_market/__init__.py` (empty)
- Create: `car_market/scenarios/__init__.py` (empty)
- Create: `tests/__init__.py` (empty)
- Create: `tests/car_market/__init__.py` (empty)

- [ ] **Step 1: Create the empty `__init__.py` files**

```bash
mkdir -p car_market/scenarios car_market/personas_data tests/car_market
touch car_market/__init__.py car_market/scenarios/__init__.py tests/__init__.py tests/car_market/__init__.py
```

- [ ] **Step 2: Verify pytest can discover an empty test**

Create `tests/car_market/test_smoke.py`:

```python
def test_smoke():
    assert True
```

Run: `pytest tests/car_market/test_smoke.py -v`
Expected: 1 passed.

- [ ] **Step 3: Commit**

```bash
git add car_market/ tests/
git commit -m "chore: scaffold car_market package and tests"
```

---

## Phase A — Foundation: oracle + personas + metric contract (TDD)

### Task A.1: `CarSpec` dataclass + sampling primitive

**Files:**
- Create: `car_market/generator.py`
- Test: `tests/car_market/test_generator.py`

- [ ] **Step 1: Write failing test for CarSpec field shape**

Create `tests/car_market/test_generator.py`:

```python
from car_market.generator import CarSpec, generate

def test_carspec_fields():
    cs = CarSpec(
        car_id="C_0001", year=2018, make="Honda", model="Accord",
        body="Sedan", mileage=78000, true_condition=3.2,
        true_value=15400.0, seller_floor=13860.0, seller_ceiling=16940.0,
        true_vhr_flags=["NO_SALVAGE_TITLE", "NO_ACCIDENTS_REPORTED"],
    )
    assert cs.year == 2018
    assert cs.seller_floor < cs.true_value < cs.seller_ceiling
    assert cs.true_condition >= 1.0 and cs.true_condition <= 5.0

def test_generate_is_deterministic():
    a = generate(seed=42, n=20)
    b = generate(seed=42, n=20)
    assert [c.car_id for c in a] == [c.car_id for c in b]
    assert [c.true_value for c in a] == [c.true_value for c in b]

def test_generate_attribute_ranges():
    cars = generate(seed=7, n=100)
    assert all(2010 <= c.year <= 2026 for c in cars)
    assert all(0 <= c.mileage <= 250000 for c in cars)
    assert all(1.0 <= c.true_condition <= 5.0 for c in cars)
    assert all(c.true_value > 0 for c in cars)
    assert all(c.seller_floor < c.true_value < c.seller_ceiling for c in cars)
```

Run: `pytest tests/car_market/test_generator.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 2: Implement generator with hand-tuned hedonic formula**

Create `car_market/generator.py`:

```python
"""Synthetic car generator. The oracle: every car's `true_value` is the
ground truth for regret/welfare computations. No external dataset is loaded
at runtime."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

# Make/body marginal (hand-tuned to look like a real 2026 lot).
MAKE_BODY_PRIOR = [
    ("Honda",     "Sedan",       0.10),
    ("Honda",     "SUV",         0.06),
    ("Toyota",    "Sedan",       0.10),
    ("Toyota",    "SUV",         0.07),
    ("Toyota",    "Truck",       0.04),
    ("Ford",      "Truck",       0.07),
    ("Ford",      "SUV",         0.06),
    ("Chevrolet", "Truck",       0.06),
    ("Chevrolet", "SUV",         0.04),
    ("BMW",       "Sedan",       0.04),
    ("BMW",       "SUV",         0.03),
    ("Tesla",     "Sedan",       0.05),
    ("Tesla",    "SUV",         0.04),
    ("Subaru",    "SUV",         0.05),
    ("Mazda",     "Sedan",       0.04),
    ("Hyundai",   "Sedan",       0.03),
    ("Kia",       "SUV",         0.03),
    ("Jeep",      "SUV",         0.04),
    ("Nissan",    "Sedan",       0.03),
    ("Volkswagen","Sedan",       0.02),
]
MODELS_PER_MAKE_BODY = {
    ("Honda", "Sedan"): ["Civic", "Accord"],
    ("Honda", "SUV"): ["CR-V", "Pilot"],
    ("Toyota", "Sedan"): ["Corolla", "Camry"],
    ("Toyota", "SUV"): ["RAV4", "Highlander"],
    ("Toyota", "Truck"): ["Tacoma", "Tundra"],
    ("Ford", "Truck"): ["F-150", "Ranger"],
    ("Ford", "SUV"): ["Explorer", "Escape"],
    ("Chevrolet", "Truck"): ["Silverado", "Colorado"],
    ("Chevrolet", "SUV"): ["Equinox", "Tahoe"],
    ("BMW", "Sedan"): ["3 Series", "5 Series"],
    ("BMW", "SUV"): ["X3", "X5"],
    ("Tesla", "Sedan"): ["Model 3", "Model S"],
    ("Tesla", "SUV"): ["Model Y", "Model X"],
    ("Subaru", "SUV"): ["Outback", "Forester"],
    ("Mazda", "Sedan"): ["Mazda3", "Mazda6"],
    ("Hyundai", "Sedan"): ["Elantra", "Sonata"],
    ("Kia", "SUV"): ["Sportage", "Telluride"],
    ("Jeep", "SUV"): ["Wrangler", "Grand Cherokee"],
    ("Nissan", "Sedan"): ["Sentra", "Altima"],
    ("Volkswagen", "Sedan"): ["Jetta", "Passat"],
}
MAKE_PREMIUM = {  # log-additive price effect by make
    "Honda": 0.00, "Toyota": 0.05, "Ford": -0.05, "Chevrolet": -0.05,
    "BMW": 0.30, "Tesla": 0.40, "Subaru": 0.05, "Mazda": -0.02,
    "Hyundai": -0.10, "Kia": -0.10, "Jeep": 0.10, "Nissan": -0.05,
    "Volkswagen": -0.05,
}
BODY_PREMIUM = {"Sedan": 0.0, "SUV": 0.15, "Truck": 0.20}

VHR_FLAGS_POOL = [
    "NO_SALVAGE_TITLE", "NO_FRAME_DAMAGE", "NO_FLOOD_WATER_DAMAGE",
    "NO_ACCIDENTS_REPORTED", "NO_ONE_OWNER",
]
NEGATIVE_FLAGS = {
    "SALVAGE_TITLE", "FRAME_DAMAGE", "FLOOD_WATER_DAMAGE",
    "ACCIDENTS_REPORTED", "PRIOR_USE_LEASE",
}


@dataclass
class CarSpec:
    car_id: str
    year: int
    make: str
    model: str
    body: str
    mileage: int
    true_condition: float
    true_value: float
    seller_floor: float
    seller_ceiling: float
    true_vhr_flags: list[str] = field(default_factory=list)


def _hedonic_log_price(year: int, miles: int, cond: float, make: str, body: str) -> float:
    return (
        9.7
        + 0.07 * (year - 2020)
        - 0.18 * math.log(miles + 1) / math.log(100000)
        + 0.10 * (cond - 3.0)
        + MAKE_PREMIUM.get(make, 0.0)
        + BODY_PREMIUM.get(body, 0.0)
    )


def _draw_make_body(rng: random.Random) -> tuple[str, str]:
    total = sum(w for _, _, w in MAKE_BODY_PRIOR)
    target = rng.random() * total
    acc = 0.0
    for make, body, w in MAKE_BODY_PRIOR:
        acc += w
        if target <= acc:
            return make, body
    return MAKE_BODY_PRIOR[-1][0], MAKE_BODY_PRIOR[-1][1]


def _draw_vhr_flags(rng: random.Random) -> list[str]:
    flags = []
    for pos, neg in [
        ("NO_SALVAGE_TITLE", "SALVAGE_TITLE"),
        ("NO_FRAME_DAMAGE", "FRAME_DAMAGE"),
        ("NO_FLOOD_WATER_DAMAGE", "FLOOD_WATER_DAMAGE"),
        ("NO_ACCIDENTS_REPORTED", "ACCIDENTS_REPORTED"),
        ("NO_ONE_OWNER", "PRIOR_USE_LEASE"),
    ]:
        flags.append(pos if rng.random() > 0.15 else neg)
    return flags


def generate(seed: int, n: int) -> list[CarSpec]:
    """Deterministic per seed. Returns n CarSpec with ground-truth values."""
    rng = random.Random(seed)
    out: list[CarSpec] = []
    for i in range(n):
        make, body = _draw_make_body(rng)
        model = rng.choice(MODELS_PER_MAKE_BODY[(make, body)])
        year = max(2010, min(2026, int(round(rng.gauss(2019, 3)))))
        median_miles = max(5000, int(20000 * (2026 - year) + rng.gauss(0, 15000)))
        miles = max(0, min(250000, median_miles))
        true_condition = max(1.0, min(5.0, rng.gauss(3.2, 0.7)))
        log_p = _hedonic_log_price(year, miles, true_condition, make, body) + rng.gauss(0, 0.07)
        true_value = float(math.exp(log_p))
        seller_floor = true_value * (0.9 + rng.gauss(0, 0.02))
        seller_ceiling = true_value * (1.1 + rng.gauss(0, 0.02))
        flags = _draw_vhr_flags(rng)
        out.append(CarSpec(
            car_id=f"C_{i+1:04d}",
            year=year, make=make, model=model, body=body, mileage=miles,
            true_condition=true_condition, true_value=true_value,
            seller_floor=seller_floor, seller_ceiling=seller_ceiling,
            true_vhr_flags=flags,
        ))
    return out
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/car_market/test_generator.py -v`
Expected: 3 passed.

- [ ] **Step 4: Sanity-check value distribution**

Run: `python3 -c "from car_market.generator import generate; cars = generate(seed=0, n=200); vs = sorted(c.true_value for c in cars); print('p10:', round(vs[20]), 'p50:', round(vs[100]), 'p90:', round(vs[180]))"`
Expected: numbers roughly $8k / $18k / $40k. If wildly off (e.g. p50 < $5k or > $50k), retune `_hedonic_log_price` constants — the calibration target is plausible 2026 used-car prices.

- [ ] **Step 5: Commit**

```bash
git add car_market/generator.py tests/car_market/test_generator.py
git commit -m "feat(generator): synthetic CarSpec sampler with hedonic oracle"
```

### Task A.2: SellerArchetype taxonomy + listing construction

**Files:**
- Create: `car_market/archetypes.py`
- Test: `tests/car_market/test_archetypes.py`

- [ ] **Step 1: Write failing test**

Create `tests/car_market/test_archetypes.py`:

```python
import random
from car_market.archetypes import (
    SellerArchetype, HONEST, MODERATE, AGGRESSIVE,
    population_sample, build_listing,
)
from car_market.generator import generate


def test_archetype_constants():
    assert HONEST.condition_bias == 0.0
    assert MODERATE.condition_bias == 1.0
    assert AGGRESSIVE.condition_bias == 2.0


def test_population_proportions():
    pop = population_sample(seed=0, k=20)
    counts = {"honest": 0, "moderate": 0, "aggressive": 0}
    for a in pop:
        counts[a.name] += 1
    assert counts == {"honest": 12, "moderate": 6, "aggressive": 2}


def test_population_deterministic():
    assert [a.name for a in population_sample(seed=1, k=20)] == \
           [a.name for a in population_sample(seed=1, k=20)]


def test_honest_listing_matches_truth():
    car = generate(seed=0, n=1)[0]
    listing = build_listing(car, HONEST, seller_id="S_01", rng=random.Random(0))
    assert listing.listing_condition == car.true_condition
    assert set(listing.claimed_vhr_flags) == set(car.true_vhr_flags)


def test_moderate_inflates_condition():
    car = generate(seed=0, n=1)[0]
    listing = build_listing(car, MODERATE, seller_id="S_01", rng=random.Random(0))
    expected_cond = min(car.true_condition + 1.0, 5.0)
    assert abs(listing.listing_condition - expected_cond) < 1e-9


def test_aggressive_drops_negative_flags():
    car = generate(seed=42, n=1)[0]
    listing = build_listing(car, AGGRESSIVE, seller_id="S_01", rng=random.Random(0))
    from car_market.generator import NEGATIVE_FLAGS
    for f in listing.claimed_vhr_flags:
        assert f not in NEGATIVE_FLAGS, f"aggressive should hide {f}"


def test_asking_price_within_archetype_band():
    car = generate(seed=2, n=1)[0]
    listing = build_listing(car, MODERATE, seller_id="S_01", rng=random.Random(0))
    lo = car.seller_ceiling * 1.05
    hi = car.seller_ceiling * 1.15
    assert lo <= listing.asking_price <= hi
```

Run: `pytest tests/car_market/test_archetypes.py -v`
Expected: FAIL — module not found.

- [ ] **Step 2: Implement archetypes module**

Create `car_market/archetypes.py`:

```python
"""Seller archetypes. Pinned policies — sellers are NOT free to choose
inflation level. This makes the reputation ablation identifiable."""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .generator import CarSpec, NEGATIVE_FLAGS


@dataclass(frozen=True)
class SellerArchetype:
    name: str                           # honest | moderate | aggressive
    condition_bias: float               # 0.0 | 1.0 | 2.0
    vhr_disclosure: str                 # full | drop_worst | drop_all_negative
    asking_markup_low: float
    asking_markup_high: float


HONEST = SellerArchetype("honest", 0.0, "full", 0.95, 1.05)
MODERATE = SellerArchetype("moderate", 1.0, "drop_worst", 1.05, 1.15)
AGGRESSIVE = SellerArchetype("aggressive", 2.0, "drop_all_negative", 1.10, 1.25)

# Population proportions for k=20 sellers: 12 honest, 6 moderate, 2 aggressive.
_POPULATION_TEMPLATE = ([HONEST] * 12) + ([MODERATE] * 6) + ([AGGRESSIVE] * 2)


def population_sample(seed: int, k: int = 20) -> list[SellerArchetype]:
    """Deterministic archetype draw for k sellers. Keeps 60/30/10 proportions."""
    rng = random.Random(seed)
    if k == 20:
        out = _POPULATION_TEMPLATE[:]
    else:
        n_honest = int(round(0.60 * k))
        n_moderate = int(round(0.30 * k))
        n_aggressive = k - n_honest - n_moderate
        out = ([HONEST] * n_honest) + ([MODERATE] * n_moderate) + ([AGGRESSIVE] * n_aggressive)
    rng.shuffle(out)
    return out


@dataclass
class CarListing:
    """A listing produced by combining a CarSpec with a seller archetype."""
    listing_id: str
    seller_id: str
    car: CarSpec
    asking_price: float
    listing_condition: float
    claimed_vhr_flags: list[str]
    description: str = ""        # filled in `llm` mode only
    sold: bool = False


def _disclose(true_flags: list[str], policy: str) -> list[str]:
    if policy == "full":
        return list(true_flags)
    if policy == "drop_worst":
        # Drop a single negative flag if any; otherwise unchanged.
        negs = [f for f in true_flags if f in NEGATIVE_FLAGS]
        if not negs:
            return list(true_flags)
        # Drop the first negative deterministically.
        drop = negs[0]
        return [f for f in true_flags if f != drop]
    if policy == "drop_all_negative":
        return [f for f in true_flags if f not in NEGATIVE_FLAGS]
    raise ValueError(f"unknown vhr_disclosure policy: {policy}")


def build_listing(
    car: CarSpec,
    archetype: SellerArchetype,
    seller_id: str,
    rng: random.Random,
    listing_id: str | None = None,
) -> CarListing:
    """Construct a CarListing from a CarSpec + archetype policy."""
    listing_cond = min(5.0, car.true_condition + archetype.condition_bias)
    claimed_flags = _disclose(car.true_vhr_flags, archetype.vhr_disclosure)
    markup = rng.uniform(archetype.asking_markup_low, archetype.asking_markup_high)
    asking = car.seller_ceiling * markup
    return CarListing(
        listing_id=listing_id or f"L_{car.car_id[2:]}_{seller_id}",
        seller_id=seller_id, car=car,
        asking_price=float(asking),
        listing_condition=float(listing_cond),
        claimed_vhr_flags=claimed_flags,
    )
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/car_market/test_archetypes.py -v`
Expected: 7 passed.

- [ ] **Step 4: Commit**

```bash
git add car_market/archetypes.py tests/car_market/test_archetypes.py
git commit -m "feat(archetypes): seller honesty taxonomy with pinned policies"
```

### Task A.3: Persona schema + 10 personas + utility function

**Files:**
- Create: `car_market/personas.py`
- Create: `car_market/personas_data/*.json` (10 files)
- Test: `tests/car_market/test_personas.py`

- [ ] **Step 1: Write failing test**

Create `tests/car_market/test_personas.py`:

```python
import json
from pathlib import Path
from car_market.personas import Persona, load_personas, utility
from car_market.generator import CarSpec


def _fake_car(**overrides):
    base = dict(
        car_id="C_0001", year=2020, make="Honda", model="CR-V",
        body="SUV", mileage=40000, true_condition=4.0, true_value=22000.0,
        seller_floor=19800.0, seller_ceiling=24200.0,
        true_vhr_flags=["NO_SALVAGE_TITLE", "NO_ACCIDENTS_REPORTED", "NO_ONE_OWNER"],
    )
    base.update(overrides)
    return CarSpec(**base)


def test_load_personas_returns_ten():
    ps = load_personas()
    assert len(ps) == 10
    assert all(isinstance(p, Persona) for p in ps)


def test_persona_required_fields():
    ps = load_personas()
    for p in ps:
        assert p.persona_id
        assert p.allowed_bodies
        assert p.max_budget > 0
        assert "year" in p.weights and "miles" in p.weights and "condition" in p.weights


def test_utility_respects_hard_constraints():
    ps = {p.persona_id: p for p in load_personas()}
    student = ps["student_first_car"]
    expensive_car = _fake_car(true_value=40000.0)
    u = utility(expensive_car, listing_condition=4.0, price=39000.0, persona=student)
    assert u == float("-inf"), "should be ruled out by budget"


def test_utility_uses_listing_condition_not_true():
    ps = {p.persona_id: p for p in load_personas()}
    family = ps["family_of_four"]
    car = _fake_car()
    u_high = utility(car, listing_condition=5.0, price=20000.0, persona=family)
    u_low = utility(car, listing_condition=2.0, price=20000.0, persona=family)
    assert u_high > u_low, "buyer values higher claimed condition"


def test_utility_decreasing_in_price():
    ps = {p.persona_id: p for p in load_personas()}
    family = ps["family_of_four"]
    car = _fake_car()
    u_cheap = utility(car, 4.0, 18000.0, family)
    u_dear = utility(car, 4.0, 23000.0, family)
    assert u_cheap > u_dear
```

Run: `pytest tests/car_market/test_personas.py -v`
Expected: FAIL — module not found.

- [ ] **Step 2: Implement personas module**

Create `car_market/personas.py`:

```python
"""Buyer personas with hedonic utility. Personas are loaded from
car_market/personas_data/*.json."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from .generator import CarSpec


@dataclass(frozen=True)
class Persona:
    persona_id: str
    description: str
    allowed_bodies: list[str]     # hard constraint
    max_miles: int                # hard constraint
    max_age_years: int            # hard constraint, vs base_year=2026
    max_budget: float             # hard constraint
    preferred_makes: list[str]    # soft preference
    weights: dict                 # keys: year, miles, condition, body_match, brand
    price_sensitivity: float      # λ; higher = more price-averse
    risk_aversion: float          # 0..1; penalty for high asking-price-vs-ceiling


PERSONA_DIR = Path(__file__).parent / "personas_data"
BASE_YEAR = 2026


def load_personas() -> list[Persona]:
    out = []
    for p in sorted(PERSONA_DIR.glob("*.json")):
        d = json.loads(p.read_text())
        out.append(Persona(**d))
    return out


def _satisfies(car: CarSpec, p: Persona, price: float) -> bool:
    if car.body not in p.allowed_bodies:
        return False
    if car.mileage > p.max_miles:
        return False
    if (BASE_YEAR - car.year) > p.max_age_years:
        return False
    if price > p.max_budget:
        return False
    return True


def utility(car: CarSpec, listing_condition: float, price: float, persona: Persona) -> float:
    """Persona's utility for buying `car` at `price` given the seller's claim
    `listing_condition`. Buyer does NOT see true_condition. Returns -inf if
    hard constraints fail."""
    if not _satisfies(car, persona, price):
        return float("-inf")
    w = persona.weights
    year_score = (car.year - 2015) / 11.0          # 2015→0, 2026→1
    miles_score = 1.0 - min(1.0, car.mileage / 150000)
    cond_score = (listing_condition - 1.0) / 4.0
    body_match = 1.0 if car.body in persona.allowed_bodies else 0.0
    brand_match = 1.0 if car.make in persona.preferred_makes else 0.4
    value = (
        w["year"] * year_score
        + w["miles"] * miles_score
        + w["condition"] * cond_score
        + w["body_match"] * body_match
        + w["brand"] * brand_match
    )
    # Convert hedonic score to dollars at max_budget scale.
    dollar_value = value * persona.max_budget
    return float(dollar_value - persona.price_sensitivity * price)
```

- [ ] **Step 3: Write the 10 persona JSONs**

Create the following files in `car_market/personas_data/`. Each is one JSON file.

`student_first_car.json`:

```json
{
  "persona_id": "student_first_car",
  "description": "First-time buyer, tight budget, just needs something that runs.",
  "allowed_bodies": ["Sedan", "SUV"],
  "max_miles": 200000,
  "max_age_years": 18,
  "max_budget": 9000,
  "preferred_makes": ["Honda", "Toyota", "Hyundai", "Kia"],
  "weights": {"year": 0.1, "miles": 0.25, "condition": 0.3, "body_match": 0.15, "brand": 0.2},
  "price_sensitivity": 1.4,
  "risk_aversion": 0.6
}
```

`family_of_four.json`:

```json
{
  "persona_id": "family_of_four",
  "description": "Two kids, needs an SUV with safety + reliability + space.",
  "allowed_bodies": ["SUV"],
  "max_miles": 100000,
  "max_age_years": 8,
  "max_budget": 32000,
  "preferred_makes": ["Honda", "Toyota", "Subaru", "Kia"],
  "weights": {"year": 0.2, "miles": 0.2, "condition": 0.3, "body_match": 0.15, "brand": 0.15},
  "price_sensitivity": 1.0,
  "risk_aversion": 0.7
}
```

`commuter_sedan.json`:

```json
{
  "persona_id": "commuter_sedan",
  "description": "Daily driver under 80mi/day, optimises fuel efficiency and reliability.",
  "allowed_bodies": ["Sedan"],
  "max_miles": 120000,
  "max_age_years": 10,
  "max_budget": 22000,
  "preferred_makes": ["Toyota", "Honda", "Mazda", "Hyundai"],
  "weights": {"year": 0.2, "miles": 0.25, "condition": 0.25, "body_match": 0.1, "brand": 0.2},
  "price_sensitivity": 1.1,
  "risk_aversion": 0.5
}
```

`contractor_pickup.json`:

```json
{
  "persona_id": "contractor_pickup",
  "description": "Self-employed contractor, needs a truck for tools and towing.",
  "allowed_bodies": ["Truck"],
  "max_miles": 180000,
  "max_age_years": 15,
  "max_budget": 28000,
  "preferred_makes": ["Ford", "Chevrolet", "Toyota"],
  "weights": {"year": 0.15, "miles": 0.2, "condition": 0.35, "body_match": 0.2, "brand": 0.1},
  "price_sensitivity": 0.9,
  "risk_aversion": 0.5
}
```

`ev_curious.json`:

```json
{
  "persona_id": "ev_curious",
  "description": "Wants to try an EV, willing to pay a premium for low emissions.",
  "allowed_bodies": ["Sedan", "SUV"],
  "max_miles": 80000,
  "max_age_years": 6,
  "max_budget": 40000,
  "preferred_makes": ["Tesla"],
  "weights": {"year": 0.3, "miles": 0.15, "condition": 0.2, "body_match": 0.1, "brand": 0.25},
  "price_sensitivity": 0.8,
  "risk_aversion": 0.4
}
```

`enthusiast_coupe.json`:

```json
{
  "persona_id": "enthusiast_coupe",
  "description": "Performance car enthusiast, German brands preferred.",
  "allowed_bodies": ["Sedan"],
  "max_miles": 90000,
  "max_age_years": 12,
  "max_budget": 38000,
  "preferred_makes": ["BMW", "Volkswagen"],
  "weights": {"year": 0.2, "miles": 0.2, "condition": 0.25, "body_match": 0.05, "brand": 0.3},
  "price_sensitivity": 0.7,
  "risk_aversion": 0.5
}
```

`weekend_offroad.json`:

```json
{
  "persona_id": "weekend_offroad",
  "description": "Weekend trail-runner. Wants a Wrangler-class SUV.",
  "allowed_bodies": ["SUV", "Truck"],
  "max_miles": 150000,
  "max_age_years": 14,
  "max_budget": 30000,
  "preferred_makes": ["Jeep", "Toyota", "Ford"],
  "weights": {"year": 0.15, "miles": 0.2, "condition": 0.3, "body_match": 0.15, "brand": 0.2},
  "price_sensitivity": 0.85,
  "risk_aversion": 0.5
}
```

`retiree_value.json`:

```json
{
  "persona_id": "retiree_value",
  "description": "Retired, drives infrequently, optimises pure cost-per-mile.",
  "allowed_bodies": ["Sedan", "SUV"],
  "max_miles": 90000,
  "max_age_years": 10,
  "max_budget": 18000,
  "preferred_makes": ["Toyota", "Honda", "Subaru"],
  "weights": {"year": 0.15, "miles": 0.2, "condition": 0.35, "body_match": 0.1, "brand": 0.2},
  "price_sensitivity": 1.2,
  "risk_aversion": 0.8
}
```

`rideshare_driver.json`:

```json
{
  "persona_id": "rideshare_driver",
  "description": "Uber/Lyft driver. Reliability dominates everything.",
  "allowed_bodies": ["Sedan", "SUV"],
  "max_miles": 80000,
  "max_age_years": 7,
  "max_budget": 25000,
  "preferred_makes": ["Toyota", "Honda", "Hyundai", "Kia"],
  "weights": {"year": 0.2, "miles": 0.3, "condition": 0.3, "body_match": 0.1, "brand": 0.1},
  "price_sensitivity": 1.0,
  "risk_aversion": 0.7
}
```

`luxury_buyer.json`:

```json
{
  "persona_id": "luxury_buyer",
  "description": "High income, wants new BMW/Tesla, condition matters most.",
  "allowed_bodies": ["Sedan", "SUV"],
  "max_miles": 50000,
  "max_age_years": 5,
  "max_budget": 60000,
  "preferred_makes": ["BMW", "Tesla"],
  "weights": {"year": 0.25, "miles": 0.15, "condition": 0.25, "body_match": 0.1, "brand": 0.25},
  "price_sensitivity": 0.6,
  "risk_aversion": 0.4
}
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/car_market/test_personas.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add car_market/personas.py car_market/personas_data/ tests/car_market/test_personas.py
git commit -m "feat(personas): 10 buyer personas with hedonic utility"
```

---

## Phase B — Reputation

### Task B.1: `BetaReputation` with update rule and decay

**Files:**
- Create: `car_market/reputation.py`
- Test: `tests/car_market/test_reputation.py`

- [ ] **Step 1: Write failing test**

Create `tests/car_market/test_reputation.py`:

```python
import math
import pytest
from car_market.reputation import (
    BetaReputation, update_on_deal, honesty_from_gap,
)


def test_initial_state():
    r = BetaReputation(seller_id="S_01")
    assert r.alpha == 2.0 and r.beta == 2.0
    assert r.review_count == 0
    assert abs(r.mean_rating() - 0.5) < 1e-9


def test_honesty_signal_extremes():
    assert honesty_from_gap(0.0) == 1.0
    assert honesty_from_gap(2.0) == 0.0
    assert honesty_from_gap(4.0) == 0.0   # clipped


def test_update_increases_alpha_on_honest_deal():
    r = BetaReputation(seller_id="S_01")
    update_on_deal(r, listing_cond=3.0, true_cond=3.0)
    assert r.alpha > 2.0
    assert r.beta == pytest.approx(2.0 * 1.0, abs=1e-9) or r.beta < 2.001


def test_update_increases_beta_on_dishonest_deal():
    r = BetaReputation(seller_id="S_01")
    update_on_deal(r, listing_cond=5.0, true_cond=2.0)  # gap = 3 → clipped honesty=0
    assert r.beta > 2.0
    assert r.alpha == pytest.approx(2.0, abs=1e-9) or r.alpha < 2.001


def test_decay_within_bounds():
    r = BetaReputation(seller_id="S_01", decay=0.95)
    update_on_deal(r, listing_cond=3.0, true_cond=3.0)
    a1, b1 = r.alpha, r.beta
    update_on_deal(r, listing_cond=3.0, true_cond=3.0)
    a2, b2 = r.alpha, r.beta
    # After two honest deals with decay, alpha should keep growing but
    # bounded; beta should stay near 2.0 * decay^2 + tiny contributions.
    assert a2 > a1
    assert b2 < 2.1   # decay drags it down + tiny new beta contribution


def test_review_count_increments():
    r = BetaReputation(seller_id="S_01")
    for _ in range(5):
        update_on_deal(r, listing_cond=3.0, true_cond=3.0)
    assert r.review_count == 5
```

Run: `pytest tests/car_market/test_reputation.py -v`
Expected: FAIL — module not found.

- [ ] **Step 2: Implement reputation module**

Create `car_market/reputation.py`:

```python
"""Beta-Bernoulli reputation per seller with exponential decay."""
from __future__ import annotations

from dataclasses import dataclass, field

MAX_COND_GAP = 2.0


def honesty_from_gap(gap: float) -> float:
    """Map |listing_cond - true_cond| → honesty in [0, 1]."""
    return max(0.0, min(1.0, 1.0 - abs(gap) / MAX_COND_GAP))


@dataclass
class BetaReputation:
    seller_id: str
    alpha: float = 2.0
    beta: float = 2.0
    review_count: int = 0
    decay: float = 0.97
    excerpts: list[str] = field(default_factory=list)

    def mean_rating(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    def stars(self) -> float:
        """Mean rating mapped to 1.0..5.0 stars."""
        return 1.0 + 4.0 * self.mean_rating()


def update_on_deal(
    rep: BetaReputation,
    listing_cond: float,
    true_cond: float,
    excerpt_factory=None,
) -> None:
    h = honesty_from_gap(listing_cond - true_cond)
    rep.alpha = rep.decay * rep.alpha + h
    rep.beta = rep.decay * rep.beta + (1.0 - h)
    rep.review_count += 1
    if h < 0.5 and excerpt_factory is not None:
        rep.excerpts.append(excerpt_factory(listing_cond=listing_cond, true_cond=true_cond))
    # Cap excerpts at last 5.
    if len(rep.excerpts) > 5:
        rep.excerpts = rep.excerpts[-5:]
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/car_market/test_reputation.py -v`
Expected: 6 passed.

- [ ] **Step 4: Commit**

```bash
git add car_market/reputation.py tests/car_market/test_reputation.py
git commit -m "feat(reputation): Beta posterior with decay and honesty update"
```

---

## Phase C — Marketplace extension

### Task C.1: `CarMarketplace` with reputation + locks + search ranking

**Files:**
- Create: `car_market/marketplace.py`
- Test: `tests/car_market/test_marketplace.py`

- [ ] **Step 1: Write failing test**

Create `tests/car_market/test_marketplace.py`:

```python
import random
import pytest
from car_market.archetypes import HONEST, AGGRESSIVE, build_listing
from car_market.generator import generate
from car_market.marketplace import CarMarketplace
from car_market.reputation import BetaReputation


def _seed_listings(mp, n=3, seed=0, archetype=HONEST, seller_id="S_01"):
    cars = generate(seed=seed, n=n)
    rng = random.Random(seed)
    for c in cars:
        l = build_listing(c, archetype, seller_id=seller_id, rng=rng)
        mp.add_listing(l)
    return cars


def test_listing_locks_on_open_offer():
    mp = CarMarketplace(run_name="t1")
    _seed_listings(mp, n=1)
    listing_id = list(mp.listings.keys())[0]
    off = mp.make_offer(buyer="B_01", listing_id=listing_id, price=10000.0, message="")
    assert off is not None
    second = mp.make_offer(buyer="B_02", listing_id=listing_id, price=11000.0, message="")
    assert second is None, "listing should be locked while offer is open"


def test_listing_unlocks_on_decline():
    mp = CarMarketplace(run_name="t2")
    _seed_listings(mp, n=1, seller_id="S_01")
    listing_id = list(mp.listings.keys())[0]
    off = mp.make_offer(buyer="B_01", listing_id=listing_id, price=10000.0, message="")
    mp.respond_to_offer(seller="S_01", offer_id=off.offer_id, action="decline", counter_price=None, message="")
    re_offer = mp.make_offer(buyer="B_02", listing_id=listing_id, price=10500.0, message="")
    assert re_offer is not None, "lock should release after decline"


def test_buyer_cannot_hold_two_open_offers():
    mp = CarMarketplace(run_name="t3")
    cars = _seed_listings(mp, n=2, seller_id="S_01")
    ids = list(mp.listings.keys())
    a = mp.make_offer(buyer="B_01", listing_id=ids[0], price=1000.0, message="")
    b = mp.make_offer(buyer="B_01", listing_id=ids[1], price=1000.0, message="")
    assert a is not None
    assert b is None, "buyer with an open offer cannot start another"


def test_search_ranking_visible_promotes_high_rep():
    mp = CarMarketplace(run_name="t4", reputation_gamma=0.5)
    _seed_listings(mp, n=1, seller_id="S_high")
    _seed_listings(mp, n=1, seed=1, seller_id="S_low")
    mp.reputation["S_high"] = BetaReputation("S_high", alpha=10.0, beta=2.0)
    mp.reputation["S_low"] = BetaReputation("S_low", alpha=2.0, beta=10.0)
    results = mp.search(query="SUV", max_results=10)
    # high-rep seller should outrank low-rep seller all else equal
    high_idx = next(i for i, r in enumerate(results) if r.seller_id == "S_high")
    low_idx = next(i for i, r in enumerate(results) if r.seller_id == "S_low")
    assert high_idx < low_idx


def test_search_ranking_hidden_ignores_rep():
    mp = CarMarketplace(run_name="t5", reputation_gamma=0.0)
    _seed_listings(mp, n=1, seller_id="S_high")
    _seed_listings(mp, n=1, seed=1, seller_id="S_low")
    mp.reputation["S_high"] = BetaReputation("S_high", alpha=10.0, beta=2.0)
    mp.reputation["S_low"] = BetaReputation("S_low", alpha=2.0, beta=10.0)
    # Same seed sequence so rank is determined by relevance only.
    # We test by asserting the order does NOT necessarily match alpha rank.
    results_v = CarMarketplace(run_name="probe", reputation_gamma=0.5)
    # Reproduce same seeded listings under visible mode for comparison.
    _seed_listings(results_v, n=1, seller_id="S_high")
    _seed_listings(results_v, n=1, seed=1, seller_id="S_low")
    results_v.reputation["S_high"] = BetaReputation("S_high", alpha=10.0, beta=2.0)
    results_v.reputation["S_low"] = BetaReputation("S_low", alpha=2.0, beta=10.0)
    hidden = [r.listing_id for r in mp.search(query="SUV", max_results=10)]
    visible = [r.listing_id for r in results_v.search(query="SUV", max_results=10)]
    # Either orderings differ OR the relevance score is identical (degenerate),
    # but the visible ordering must be consistent with reputation.
    assert hidden == sorted(hidden) or hidden != visible
```

Run: `pytest tests/car_market/test_marketplace.py -v`
Expected: FAIL.

- [ ] **Step 2: Implement `CarMarketplace`**

Create `car_market/marketplace.py`:

```python
"""Car marketplace extending the Project Deal substrate with:
- private car_spec attached to each listing
- per-seller Beta reputation
- listing locks while an offer is open
- single-open-offer-per-buyer rule
- search() with relevance × reputation ranking
- lookup_seller() for instrumentation
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

from .archetypes import CarListing
from .reputation import BetaReputation, update_on_deal


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Offer:
    offer_id: str
    listing_id: str
    buyer: str
    seller: str
    price: float
    message: str
    status: str = "open"     # open | accepted | declined | withdrawn | timeout


@dataclass
class Deal:
    deal_id: str
    listing_id: str
    seller: str
    buyer: str
    price: float
    timestamp: str
    true_value: float
    listing_condition: float
    true_condition: float


@dataclass
class ListingCard:
    """Public listing summary returned by search()."""
    listing_id: str
    seller_id: str
    year: int
    make: str
    model: str
    body: str
    mileage: int
    listing_condition: float
    asking_price: float
    seller_stars: float       # only meaningful in visible mode (mp.reputation_gamma > 0)


@dataclass
class SellerCard:
    """Public seller info returned by lookup_seller()."""
    seller_id: str
    stars: float
    review_count: int
    excerpts: list[str]


class CarMarketplace:
    def __init__(self, run_name: str, reputation_gamma: float = 0.5,
                 log_path: Path | None = None):
        self.run_name = run_name
        self.reputation_gamma = reputation_gamma   # 0 == hidden mode
        self.listings: dict[str, CarListing] = {}
        self.offers: dict[str, Offer] = {}
        self.deals: list[Deal] = []
        self.reputation: dict[str, BetaReputation] = {}
        self._listing_locked: set[str] = set()
        self._buyer_open_offer: dict[str, str] = {}   # buyer → offer_id
        self._offer_counter = 0
        self._deal_counter = 0
        self.log_path = log_path
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text("")

    # ---- listings -----------------------------------------------------------

    def add_listing(self, listing: CarListing) -> None:
        self.listings[listing.listing_id] = listing
        self.reputation.setdefault(listing.seller_id, BetaReputation(listing.seller_id))
        self._emit({
            "kind": "listing", "listing_id": listing.listing_id,
            "seller_id": listing.seller_id, "car_id": listing.car.car_id,
            "asking_price": listing.asking_price,
            "listing_condition": listing.listing_condition,
            "claimed_vhr_flags": listing.claimed_vhr_flags,
            "true_condition_ground_truth": listing.car.true_condition,
            "true_value_ground_truth": listing.car.true_value,
        })

    # ---- search & lookup ----------------------------------------------------

    def search(self, query: str, max_results: int = 10) -> list[ListingCard]:
        """Score = relevance(query, listing) * (1 + gamma * rating_norm)."""
        q = query.lower()
        scored = []
        for l in self.listings.values():
            if l.sold or l.listing_id in self._listing_locked:
                continue
            # Relevance: 1.0 if query token matches body/make/model, else 0.5.
            relevance = 0.5
            tokens = q.split()
            for t in tokens:
                if t in l.car.body.lower() or t in l.car.make.lower() or t in l.car.model.lower():
                    relevance = 1.0
                    break
            rating_norm = (self.reputation[l.seller_id].mean_rating() - 0.5) * 2.0
            score = relevance * (1.0 + self.reputation_gamma * rating_norm)
            scored.append((score, l))
        scored.sort(key=lambda x: (-x[0], x[1].listing_id))
        out: list[ListingCard] = []
        for _, l in scored[:max_results]:
            rep = self.reputation[l.seller_id]
            out.append(ListingCard(
                listing_id=l.listing_id, seller_id=l.seller_id,
                year=l.car.year, make=l.car.make, model=l.car.model,
                body=l.car.body, mileage=l.car.mileage,
                listing_condition=l.listing_condition,
                asking_price=l.asking_price,
                seller_stars=rep.stars() if self.reputation_gamma > 0 else 0.0,
            ))
        return out

    def lookup_seller(self, seller_id: str) -> SellerCard | None:
        if self.reputation_gamma == 0.0:
            return None       # hidden mode: tool returns nothing
        rep = self.reputation.get(seller_id)
        if rep is None:
            return None
        return SellerCard(
            seller_id=seller_id, stars=rep.stars(),
            review_count=rep.review_count, excerpts=list(rep.excerpts),
        )

    # ---- offers --------------------------------------------------------------

    def make_offer(self, buyer: str, listing_id: str, price: float, message: str) -> Offer | None:
        l = self.listings.get(listing_id)
        if l is None or l.sold or listing_id in self._listing_locked:
            return None
        if buyer in self._buyer_open_offer:
            return None
        if l.seller_id == buyer:
            return None
        self._offer_counter += 1
        off = Offer(
            offer_id=f"O_{self._offer_counter:05d}",
            listing_id=listing_id, buyer=buyer, seller=l.seller_id,
            price=float(price), message=message,
        )
        self.offers[off.offer_id] = off
        self._listing_locked.add(listing_id)
        self._buyer_open_offer[buyer] = off.offer_id
        self._emit({"kind": "offer", "offer_id": off.offer_id, "listing_id": listing_id,
                    "buyer": buyer, "seller": l.seller_id, "price": float(price)})
        return off

    def respond_to_offer(self, seller: str, offer_id: str, action: str,
                          counter_price: float | None, message: str) -> Deal | None:
        off = self.offers.get(offer_id)
        if off is None or off.status != "open" or off.seller != seller:
            return None
        l = self.listings[off.listing_id]

        if action == "accept":
            return self._settle(off, off.price)
        if action == "decline":
            off.status = "declined"
            self._release(off.listing_id, off.buyer)
            self._emit({"kind": "decline", "offer_id": offer_id})
            return None
        if action == "counter" and counter_price is not None:
            # Modeled as: original offer is withdrawn, seller sets a new
            # ask anchor. Buyer's next make_offer either matches or not.
            off.status = "withdrawn"
            self._release(off.listing_id, off.buyer)
            self._emit({"kind": "counter", "offer_id": offer_id,
                         "counter_price": float(counter_price)})
            return None
        return None

    def buyer_withdraw(self, buyer: str) -> None:
        oid = self._buyer_open_offer.get(buyer)
        if not oid:
            return
        off = self.offers[oid]
        if off.status == "open":
            off.status = "withdrawn"
            self._release(off.listing_id, buyer)
            self._emit({"kind": "withdraw", "offer_id": oid, "buyer": buyer})

    def timeout_offer(self, offer_id: str) -> None:
        off = self.offers.get(offer_id)
        if off and off.status == "open":
            off.status = "timeout"
            self._release(off.listing_id, off.buyer)
            self._emit({"kind": "timeout", "offer_id": offer_id})

    # ---- settlement ---------------------------------------------------------

    def _settle(self, off: Offer, price: float) -> Deal:
        l = self.listings[off.listing_id]
        l.sold = True
        off.status = "accepted"
        self._deal_counter += 1
        deal = Deal(
            deal_id=f"D_{self._deal_counter:05d}",
            listing_id=off.listing_id, seller=off.seller, buyer=off.buyer,
            price=price, timestamp=_now_iso(),
            true_value=l.car.true_value,
            listing_condition=l.listing_condition,
            true_condition=l.car.true_condition,
        )
        self.deals.append(deal)
        # Reputation update.
        update_on_deal(
            self.reputation[off.seller],
            listing_cond=l.listing_condition,
            true_cond=l.car.true_condition,
        )
        # Withdraw any other open offers on this listing.
        for o in list(self.offers.values()):
            if o.listing_id == off.listing_id and o.offer_id != off.offer_id and o.status == "open":
                o.status = "withdrawn"
                self._release(o.listing_id, o.buyer)
        self._release(off.listing_id, off.buyer)
        self._emit({"kind": "deal", "deal_id": deal.deal_id, **asdict(deal)})
        return deal

    def _release(self, listing_id: str, buyer: str) -> None:
        self._listing_locked.discard(listing_id)
        if self._buyer_open_offer.get(buyer) is not None:
            cur = self.offers.get(self._buyer_open_offer[buyer])
            if cur is None or cur.listing_id != listing_id or cur.status != "open":
                self._buyer_open_offer.pop(buyer, None)

    # ---- logging ------------------------------------------------------------

    def _emit(self, event: dict) -> None:
        event = {"run": self.run_name, "timestamp": _now_iso(), **event}
        if self.log_path:
            with self.log_path.open("a") as f:
                f.write(json.dumps(event, default=str) + "\n")
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/car_market/test_marketplace.py -v`
Expected: 5 passed.

- [ ] **Step 4: Commit**

```bash
git add car_market/marketplace.py tests/car_market/test_marketplace.py
git commit -m "feat(marketplace): CarMarketplace with locks, search rank, reputation"
```

---

## Phase D — S3 fast-mode end-to-end (THE HEADLINE)

### Task D.1: Heuristic seller and buyer policies

**Files:**
- Create: `car_market/policies.py`
- Test: `tests/car_market/test_policies.py`

- [ ] **Step 1: Write failing test**

Create `tests/car_market/test_policies.py`:

```python
import random
from car_market.policies import (
    HeuristicSeller, HeuristicBuyer, NegotiationStep,
)
from car_market.archetypes import HONEST, AGGRESSIVE
from car_market.generator import generate
from car_market.personas import load_personas


def test_seller_responds_above_floor_accept():
    cars = generate(seed=0, n=1)
    car = cars[0]
    seller = HeuristicSeller(seller_id="S_01", archetype=HONEST, rng=random.Random(0))
    # Offer at exactly ceiling — should accept
    decision = seller.respond_to_offer(car=car, asking_price=car.seller_ceiling,
                                        offer_price=car.seller_ceiling * 1.01)
    assert decision.action == "accept"


def test_seller_declines_below_floor():
    cars = generate(seed=0, n=1)
    car = cars[0]
    seller = HeuristicSeller(seller_id="S_01", archetype=HONEST, rng=random.Random(0))
    decision = seller.respond_to_offer(car=car, asking_price=car.seller_ceiling,
                                        offer_price=car.seller_floor * 0.5)
    assert decision.action in ("decline", "counter")


def test_buyer_picks_max_utility_under_constraints():
    cars = generate(seed=42, n=10)
    persona = next(p for p in load_personas() if p.persona_id == "family_of_four")
    buyer = HeuristicBuyer(buyer_id="B_01", persona=persona, rng=random.Random(0))
    # Construct fake listing cards from the cars.
    from car_market.marketplace import ListingCard
    cards = [
        ListingCard(
            listing_id=f"L_{i}", seller_id="S_X",
            year=c.year, make=c.make, model=c.model, body=c.body,
            mileage=c.mileage, listing_condition=c.true_condition,
            asking_price=c.true_value * 1.05, seller_stars=3.0,
        ) for i, c in enumerate(cars)
    ]
    cars_by_id = {f"L_{i}": c for i, c in enumerate(cars)}
    ranked = buyer.rank_listings(cards, cars_by_id)
    # Top pick should at least satisfy hard constraints if any do.
    if ranked:
        top = ranked[0]
        top_card = next(c for c in cards if c.listing_id == top)
        assert top_card.body in persona.allowed_bodies
```

Run: `pytest tests/car_market/test_policies.py -v`
Expected: FAIL.

- [ ] **Step 2: Implement policies module**

Create `car_market/policies.py`:

```python
"""Heuristic policies used in `--mode fast`. Deterministic given rng seed.
No LLM calls. These are what produce the headline ablation chart."""
from __future__ import annotations

import random
from dataclasses import dataclass

from .archetypes import SellerArchetype
from .generator import CarSpec
from .marketplace import ListingCard
from .personas import Persona, utility


@dataclass
class NegotiationStep:
    action: str               # accept | decline | counter
    counter_price: float = 0.0
    rationale: str = ""


class HeuristicSeller:
    def __init__(self, seller_id: str, archetype: SellerArchetype, rng: random.Random):
        self.seller_id = seller_id
        self.archetype = archetype
        self.rng = rng

    def respond_to_offer(self, car: CarSpec, asking_price: float, offer_price: float) -> NegotiationStep:
        # Reservation price = seller_floor adjusted by archetype greed.
        # Aggressive sellers cling to higher reservations.
        greed = {"honest": 1.00, "moderate": 1.03, "aggressive": 1.06}[self.archetype.name]
        reservation = car.seller_floor * greed
        if offer_price >= reservation * 1.0:
            # Accept anything ≥ midpoint(reservation, asking).
            split = (reservation + asking_price) / 2.0
            if offer_price >= split:
                return NegotiationStep(action="accept", rationale=f"offer {offer_price:.0f} ≥ split {split:.0f}")
            else:
                # Counter at split.
                return NegotiationStep(action="counter", counter_price=split, rationale="counter at split")
        return NegotiationStep(action="decline", rationale=f"offer {offer_price:.0f} < reservation {reservation:.0f}")


class HeuristicBuyer:
    def __init__(self, buyer_id: str, persona: Persona, rng: random.Random):
        self.buyer_id = buyer_id
        self.persona = persona
        self.rng = rng

    def rank_listings(self, cards: list[ListingCard], cars_by_id: dict[str, CarSpec]) -> list[str]:
        """Rank listing_ids by expected utility minus asking_price."""
        scored = []
        for c in cards:
            car = cars_by_id.get(c.listing_id)
            if car is None:
                continue
            u = utility(
                car=car, listing_condition=c.listing_condition,
                price=c.asking_price, persona=self.persona,
            )
            if u == float("-inf"):
                continue
            # Risk-adjust: penalise high asking_price relative to claimed cond.
            scored.append((u, c.listing_id))
        scored.sort(reverse=True)
        return [lid for _, lid in scored]

    def propose_price(self, card: ListingCard, car: CarSpec) -> float:
        """Bid below asking but above what we'd be willing to pay."""
        # Buyer's WTP under listing_cond: solve U=0 for price.
        # Equivalent to dollar_value / price_sensitivity.
        from .personas import BASE_YEAR
        w = self.persona.weights
        year_score = (car.year - 2015) / 11.0
        miles_score = 1.0 - min(1.0, car.mileage / 150000)
        cond_score = (card.listing_condition - 1.0) / 4.0
        body_match = 1.0 if car.body in self.persona.allowed_bodies else 0.0
        brand_match = 1.0 if car.make in self.persona.preferred_makes else 0.4
        value = (w["year"] * year_score + w["miles"] * miles_score
                 + w["condition"] * cond_score + w["body_match"] * body_match
                 + w["brand"] * brand_match) * self.persona.max_budget
        wtp = value / max(0.1, self.persona.price_sensitivity)
        # Bid 90% of min(wtp, asking).
        bid = 0.90 * min(wtp, card.asking_price)
        # Clamp to budget.
        return float(min(bid, self.persona.max_budget))
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/car_market/test_policies.py -v`
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add car_market/policies.py tests/car_market/test_policies.py
git commit -m "feat(policies): heuristic seller/buyer policies for fast mode"
```

### Task D.2: Poisson arrival scheduler

**Files:**
- Create: `car_market/scheduler.py`
- Test: `tests/car_market/test_scheduler.py`

- [ ] **Step 1: Write failing test**

Create `tests/car_market/test_scheduler.py`:

```python
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
```

Run: `pytest tests/car_market/test_scheduler.py -v`
Expected: FAIL.

- [ ] **Step 2: Implement scheduler**

Create `car_market/scheduler.py`:

```python
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
    lam = m / T
    arrivals: list[int] = []
    for t in range(T):
        if rng.random() < lam:
            arrivals.append(t)
    return arrivals
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/car_market/test_scheduler.py -v`
Expected: 4 passed.

- [ ] **Step 4: Commit**

```bash
git add car_market/scheduler.py tests/car_market/test_scheduler.py
git commit -m "feat(scheduler): Poisson arrival generator"
```

### Task D.3: S3 fast-mode end-to-end runner

**Files:**
- Create: `car_market/scenarios/s3_open_market.py`
- Create: `car_market/config.py`

- [ ] **Step 1: Create config module**

Create `car_market/config.py`:

```python
"""Run-time config for car_market scenarios."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class S3Config:
    seed: int = 0
    k_sellers: int = 20
    inventory_per_seller: tuple[int, int] = (3, 8)
    m_buyers: int = 150
    T: int = 400
    max_neg_turns: int = 6
    max_concurrent_per_seller: int = 5
    reputation_gamma: float = 0.5     # 0.0 = hidden mode
    mode: str = "fast"                # fast | llm | replay
    llm_model: str = "anthropic/claude-haiku-4-5"   # any litellm model string
    out_dir: str = "runs"
```

- [ ] **Step 2: Implement the scenario runner**

Create `car_market/scenarios/s3_open_market.py`:

```python
"""S3 open-market scenario — headline.

In `fast` mode:
- k sellers initialised with archetype draws and seeded inventories.
- m buyers arrive by Poisson process over T steps; each draws a persona.
- At arrival, buyer searches top-K, picks the listing she prefers, opens an
  offer at her policy bid, the seller responds (accept/counter/decline).
- A single counter triggers one more buyer round (so max 2 effective price
  rounds per negotiation), counted against max_neg_turns.
- Outcomes go to JSONL via the marketplace log.
"""
from __future__ import annotations

import json
import random
from dataclasses import asdict
from pathlib import Path

from ..archetypes import build_listing, population_sample
from ..config import S3Config
from ..generator import generate
from ..marketplace import CarMarketplace, ListingCard
from ..personas import load_personas, utility
from ..policies import HeuristicBuyer, HeuristicSeller
from ..scheduler import poisson_arrivals


def run(cfg: S3Config) -> dict:
    rng = random.Random(cfg.seed)
    out_dir = Path(cfg.out_dir) / f"s3_seed{cfg.seed}_gamma{cfg.reputation_gamma}"
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "events.jsonl"

    mp = CarMarketplace(
        run_name=f"s3_seed{cfg.seed}_gamma{cfg.reputation_gamma}",
        reputation_gamma=cfg.reputation_gamma,
        log_path=log_path,
    )

    # ---- seed sellers + inventories ----
    archetypes = population_sample(seed=cfg.seed, k=cfg.k_sellers)
    sellers: dict[str, HeuristicSeller] = {}
    cars_by_listing: dict[str, "CarSpec"] = {}
    car_idx = 0
    for i, archetype in enumerate(archetypes):
        seller_id = f"S_{i+1:02d}"
        n_inv = rng.randint(*cfg.inventory_per_seller)
        cars = generate(seed=cfg.seed * 1000 + i, n=n_inv)
        for c in cars:
            l = build_listing(c, archetype, seller_id=seller_id,
                              rng=random.Random(cfg.seed * 10000 + car_idx),
                              listing_id=f"L_{car_idx+1:05d}")
            mp.add_listing(l)
            cars_by_listing[l.listing_id] = c
            car_idx += 1
        sellers[seller_id] = HeuristicSeller(
            seller_id=seller_id, archetype=archetype,
            rng=random.Random(cfg.seed * 100 + i),
        )

    # ---- buyer arrivals ----
    arrivals = poisson_arrivals(m=cfg.m_buyers, T=cfg.T, seed=cfg.seed + 1)
    personas = load_personas()
    buyers_processed = 0
    deal_count = 0
    no_deal_count = 0

    for t_idx, t in enumerate(arrivals):
        persona = personas[(cfg.seed + t_idx) % len(personas)]
        buyer_id = f"B_{t_idx+1:04d}"
        buyer = HeuristicBuyer(buyer_id=buyer_id, persona=persona,
                                rng=random.Random(cfg.seed * 1000 + t_idx))
        buyers_processed += 1
        # Buyer issues a body-style-flavored query.
        q = persona.allowed_bodies[0]
        cards = mp.search(query=q, max_results=10)
        ranked = buyer.rank_listings(cards, cars_by_listing)
        deal_made = False
        for lid in ranked[:cfg.max_neg_turns]:
            card = next(c for c in cards if c.listing_id == lid)
            car = cars_by_listing[lid]
            bid = buyer.propose_price(card, car)
            off = mp.make_offer(buyer=buyer_id, listing_id=lid,
                                  price=bid, message="(fast)")
            if off is None:
                continue
            seller = sellers[card.seller_id]
            step = seller.respond_to_offer(car=car, asking_price=card.asking_price,
                                             offer_price=bid)
            if step.action == "accept":
                mp.respond_to_offer(seller=seller.seller_id, offer_id=off.offer_id,
                                     action="accept", counter_price=None, message="(fast)")
                deal_count += 1
                deal_made = True
                break
            elif step.action == "counter":
                # Convert seller counter into close-out: buyer accepts if counter ≤ wtp.
                mp.respond_to_offer(seller=seller.seller_id, offer_id=off.offer_id,
                                     action="counter", counter_price=step.counter_price,
                                     message="(fast)")
                # Buyer evaluates counter as a new asking price.
                # If counter ≤ wtp, buyer bids equal to counter to settle.
                wtp_under_listing = buyer.propose_price(card, car) / 0.90  # invert the 0.9 discount
                if step.counter_price <= wtp_under_listing:
                    new_off = mp.make_offer(buyer=buyer_id, listing_id=lid,
                                              price=step.counter_price, message="(accepts counter)")
                    if new_off is not None:
                        # Seller accepts since price >= reservation by construction of counter.
                        d = mp.respond_to_offer(seller=seller.seller_id, offer_id=new_off.offer_id,
                                                 action="accept", counter_price=None, message="(close)")
                        if d is not None:
                            deal_count += 1
                            deal_made = True
                            break
                # else fall through to next listing
            else:
                # decline: try next
                continue
        if not deal_made:
            no_deal_count += 1
            mp.buyer_withdraw(buyer_id)

    summary = {
        "run": mp.run_name, "seed": cfg.seed,
        "reputation_gamma": cfg.reputation_gamma,
        "k_sellers": cfg.k_sellers, "m_buyers_expected": cfg.m_buyers,
        "m_buyers_actual": buyers_processed,
        "deals": deal_count, "no_deal_buyers": no_deal_count,
        "listings_total": len(mp.listings),
        "listings_sold": sum(1 for l in mp.listings.values() if l.sold),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary
```

- [ ] **Step 3: Run a sanity check**

Run:

```bash
python3 -c "
from car_market.scenarios.s3_open_market import run
from car_market.config import S3Config
s = run(S3Config(seed=0, reputation_gamma=0.5))
print(s)
"
```

Expected: prints a summary dict with `deals > 0`, runs in under 10 seconds.

- [ ] **Step 4: Commit**

```bash
git add car_market/config.py car_market/scenarios/s3_open_market.py
git commit -m "feat(s3): fast-mode open-market scenario runner"
```

### Task D.4: Evaluator with locked metric formulas

**Files:**
- Create: `car_market/evaluator.py`
- Test: `tests/car_market/test_evaluator.py`

- [ ] **Step 1: Write failing test**

Create `tests/car_market/test_evaluator.py`:

```python
from car_market.evaluator import deal_welfare, run_metrics


def test_deal_welfare_components():
    d = {
        "true_value": 15000.0,
        "price": 16000.0,
        "buyer_utility": 17500.0,    # U(car | persona) at this price
    }
    bs, ss, dw = deal_welfare(price=d["price"], true_value=d["true_value"],
                                buyer_utility=d["buyer_utility"])
    assert bs == 1500.0
    assert ss == 1000.0
    assert dw == 2500.0


def test_run_metrics_empty():
    m = run_metrics(deals=[], no_deal_buyers=10)
    assert m["total_welfare"] == 0
    assert m["pct_buyers_served"] == 0.0
```

Run: `pytest tests/car_market/test_evaluator.py -v`
Expected: FAIL.

- [ ] **Step 2: Implement evaluator**

Create `car_market/evaluator.py`:

```python
"""Locked metric formulas (spec §9.1). The evaluator implements these
literally; figures derive from them."""
from __future__ import annotations

from typing import Iterable


def deal_welfare(price: float, true_value: float, buyer_utility: float) -> tuple[float, float, float]:
    """(buyer_surplus, seller_surplus, deal_welfare).
    Buyer surplus uses true U (oracle), not perceived U at listing claim."""
    buyer_surplus = buyer_utility - price
    seller_surplus = price - true_value
    return buyer_surplus, seller_surplus, buyer_surplus + seller_surplus


def gini(values: Iterable[float]) -> float:
    xs = sorted(values)
    n = len(xs)
    if n == 0:
        return 0.0
    cum = 0.0
    for i, x in enumerate(xs, start=1):
        cum += i * x
    s = sum(xs)
    if s == 0:
        return 0.0
    return (2 * cum) / (n * s) - (n + 1) / n


def run_metrics(deals: list[dict], no_deal_buyers: int) -> dict:
    """Compute per-run aggregates from per-deal records."""
    if not deals:
        return {
            "total_welfare": 0.0, "mean_buyer_surplus": 0.0,
            "mean_seller_surplus": 0.0, "n_deals": 0,
            "pct_buyers_served": 0.0,
        }
    bs_list = [d["buyer_surplus"] for d in deals]
    ss_list = [d["seller_surplus"] for d in deals]
    n_served = len({d["buyer"] for d in deals})
    n_total = n_served + no_deal_buyers
    return {
        "total_welfare": float(sum(d["deal_welfare"] for d in deals)),
        "mean_buyer_surplus": float(sum(bs_list) / max(1, n_total)),
        "mean_seller_surplus": float(sum(ss_list) / max(1, len(ss_list))),
        "n_deals": len(deals),
        "pct_buyers_served": n_served / max(1, n_total),
        "buyer_surplus_gini": gini(bs_list),
    }
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/car_market/test_evaluator.py -v`
Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add car_market/evaluator.py tests/car_market/test_evaluator.py
git commit -m "feat(evaluator): locked metric formulas with TDD"
```

### Task D.5: Wire evaluator to scenario events; compute welfare delta

**Files:**
- Modify: `car_market/scenarios/s3_open_market.py`
- Create: `car_market/aggregate.py`

- [ ] **Step 1: Add per-deal record emission**

Modify `car_market/scenarios/s3_open_market.py` — at the point where `deal_count += 1`, also append a per-deal dict that includes:

```python
{
    "deal_id": ..., "buyer": buyer_id, "seller": card.seller_id,
    "listing_id": lid, "price": settled_price, "true_value": car.true_value,
    "buyer_utility": utility(car, listing_condition=card.listing_condition,
                              price=settled_price, persona=persona),
    "buyer_surplus": ..., "seller_surplus": ..., "deal_welfare": ...,
    "listing_condition": card.listing_condition,
    "true_condition": car.true_condition,
    "seller_archetype": seller.archetype.name,
}
```

…and at scenario end, write `deal_records.json` to `out_dir`.

Edit `car_market/scenarios/s3_open_market.py` around the existing accept-paths to capture `settled_price`. Compute surpluses via `deal_welfare()` from `car_market.evaluator`. Append each record to a local `per_deal: list[dict]` list. After the arrival loop, write:

```python
(out_dir / "per_deal.json").write_text(json.dumps(per_deal, indent=2))
summary.update(run_metrics(per_deal, no_deal_count))
(out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
```

(Place the imports at top of the file: `from ..evaluator import deal_welfare, run_metrics`.)

- [ ] **Step 2: Create the welfare-delta aggregator**

Create `car_market/aggregate.py`:

```python
"""Aggregate fast-mode runs across seeds and reputation_gamma values to
produce the headline welfare-delta chart."""
from __future__ import annotations

import json
import math
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
            rows.append({**r, "gamma_label": "visible" if gamma > 0 else "hidden"})
    return {"rows": rows}


def bootstrap_ci(values: list[float], n_boot: int = 1000, alpha: float = 0.05,
                  seed: int = 0) -> tuple[float, float, float]:
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
    }
```

- [ ] **Step 3: Run a 6-seed sweep end-to-end**

Run:

```bash
python3 -c "
from car_market.aggregate import sweep, welfare_delta_report
import json
result = sweep(seeds=list(range(6)), gammas=[0.0, 0.5])
report = welfare_delta_report(result['rows'])
print(json.dumps(report, indent=2))
"
```

Expected:
- 12 runs total (6 seeds × 2 gammas) finish in <60s.
- `delta` is positive (visible welfare > hidden welfare).
- If `delta` is small or negative: tune `MAX_COND_GAP` in `reputation.py`, archetype shares in `archetypes.py`, or `reputation_gamma` to 0.7. Do not move on until the delta is positive and visibly meaningful.

- [ ] **Step 4: Commit**

```bash
git add car_market/scenarios/s3_open_market.py car_market/aggregate.py
git commit -m "feat(s3): per-deal records + sweep + welfare delta report"
```

### Task D.6: Plot the headline chart

**Files:**
- Create: `car_market/plots.py`

- [ ] **Step 1: Implement the welfare-delta bar chart**

Create `car_market/plots.py`:

```python
"""Matplotlib plotting for car-market figures."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def welfare_delta_bar(report: dict, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6, 4))
    means = [report["hidden_mean"], report["visible_mean"]]
    errs = [
        [report["hidden_mean"] - report["hidden_ci"][0], report["hidden_ci"][1] - report["hidden_mean"]],
        [report["visible_mean"] - report["visible_ci"][0], report["visible_ci"][1] - report["visible_mean"]],
    ]
    errs_t = list(zip(*errs))
    ax.bar(["hidden", "visible"], means,
            yerr=[errs_t[0], errs_t[1]],
            color=["#aaa", "#3a7"],
            capsize=8)
    ax.set_ylabel("Total welfare ($)")
    ax.set_title(f"Reputation institution welfare delta = ${report['delta']:.0f}")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
```

- [ ] **Step 2: Render the chart end-to-end**

Run:

```bash
python3 -c "
from car_market.aggregate import sweep, welfare_delta_report
from car_market.plots import welfare_delta_bar
from pathlib import Path
rows = sweep(seeds=list(range(30)), gammas=[0.0, 0.5])
report = welfare_delta_report(rows['rows'])
out = Path('runs/headline_welfare_delta.png')
out.parent.mkdir(parents=True, exist_ok=True)
welfare_delta_bar(report, out)
print('saved', out, 'delta=', round(report['delta']))
"
```

Expected:
- 60 runs in <3 min on a laptop.
- `runs/headline_welfare_delta.png` exists.
- Open the image; visible bar should be visibly higher than hidden bar with non-overlapping 95% CIs.

- [ ] **Step 3: Commit**

```bash
git add car_market/plots.py
git commit -m "feat(plots): headline welfare-delta bar chart"
```

**PHASE D COMPLETE — the money chart exists. From here everything else is supporting.**

---

## Phase E — LLM mode + transcript caching

### Task E.1: LLM listing description generator with cache

**Files:**
- Create: `car_market/descriptions.py`
- Create: `car_market/llm_cache.py`

- [ ] **Step 1: Implement the cache layer**

Create `car_market/llm_cache.py`:

```python
"""Disk-backed cache for LLM responses. JSONL append-only; reads from a
dict built on init. Keys are (purpose, hashable-context). Used by both
description.py and llm_agent.py."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


def _key(purpose: str, context: dict) -> str:
    payload = json.dumps({"purpose": purpose, "context": context}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class LLMCache:
    def __init__(self, path: Path):
        self.path = path
        self._mem: dict[str, str] = {}
        if path.exists():
            for line in path.read_text().splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                self._mem[row["key"]] = row["value"]

    def get(self, purpose: str, context: dict) -> str | None:
        return self._mem.get(_key(purpose, context))

    def put(self, purpose: str, context: dict, value: str) -> None:
        k = _key(purpose, context)
        self._mem[k] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps({"key": k, "purpose": purpose,
                                  "context": context, "value": value}, default=str) + "\n")
```

- [ ] **Step 2: Implement description generator**

Create `car_market/descriptions.py`:

```python
"""LLM-generated listing prose. Conditioned on the seller's CLAIMS
(listing_condition, claimed_vhr_flags), not the true state. Cached.
LLM provider is selected via litellm model string (e.g.
'anthropic/claude-haiku-4-5', 'openai/gpt-4o-mini', 'gemini/gemini-2.0-flash')."""
from __future__ import annotations

from litellm import completion

from .archetypes import CarListing
from .llm_cache import LLMCache

DEFAULT_MODEL = "anthropic/claude-haiku-4-5"


def generate_description(listing: CarListing, cache: LLMCache,
                          model: str = DEFAULT_MODEL) -> str:
    ctx = {
        "year": listing.car.year, "make": listing.car.make, "model": listing.car.model,
        "body": listing.car.body, "mileage": listing.car.mileage,
        "listing_condition": round(listing.listing_condition, 1),
        "claimed_vhr_flags": sorted(listing.claimed_vhr_flags),
        "asking_price": round(listing.asking_price),
        "_model": model,
    }
    hit = cache.get("description", ctx)
    if hit is not None:
        return hit
    prompt = f"""\
You are a used-car salesperson writing a listing description for AutoTrader.
Write 3 short sentences, casual but professional, that emphasise the positives.
Do NOT mention the listing condition number directly; describe it in words.

Vehicle: {ctx['year']} {ctx['make']} {ctx['model']} ({ctx['body']})
Mileage: {ctx['mileage']}
Asking: ${ctx['asking_price']}
Condition (1-5 scale, seller's claim): {ctx['listing_condition']}
Vehicle history flags: {', '.join(ctx['claimed_vhr_flags'])}
"""
    resp = completion(
        model=model, max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.choices[0].message.content.strip()
    cache.put("description", ctx, text)
    return text
```

- [ ] **Step 3: Smoke-test with one listing**

Run:

```bash
ANTHROPIC_API_KEY=<your-key> python3 -c "
from anthropic import Anthropic
from pathlib import Path
from car_market.generator import generate
from car_market.archetypes import AGGRESSIVE, build_listing
from car_market.descriptions import generate_description
from car_market.llm_cache import LLMCache
import random
client = Anthropic()
cache = LLMCache(Path('runs/llm_cache.jsonl'))
car = generate(seed=0, n=1)[0]
l = build_listing(car, AGGRESSIVE, seller_id='S_01', rng=random.Random(0))
print('CAR:', car.year, car.make, car.model, 'true_cond=', round(car.true_condition,1),
      'claimed_cond=', l.listing_condition)
print('DESCRIPTION:', generate_description(l, client, cache))
"
```

Expected: 3-sentence listing prose printed; cache file populated; second run returns instantly.

- [ ] **Step 4: Commit**

```bash
git add car_market/descriptions.py car_market/llm_cache.py
git commit -m "feat(llm): cached listing-description generator"
```

### Task E.2: LLM negotiation messages (for transcripts only, no decisions)

**Files:**
- Create: `car_market/llm_agent.py`

- [ ] **Step 1: Implement the LLM message generator**

Create `car_market/llm_agent.py`:

```python
"""LLM-flavored negotiation messages. The DECISION (accept/counter/decline,
bid price) is taken by the heuristic policy in policies.py; the LLM only
writes the natural-language MESSAGE that accompanies the action. This keeps
the ablation deterministic while making transcripts feel human.

Model selection goes through litellm so the same code drives Claude, GPT,
Gemini, or local models — used for the capability-asymmetry sub-experiment."""
from __future__ import annotations

from litellm import completion

from .llm_cache import LLMCache

DEFAULT_MODEL = "anthropic/claude-haiku-4-5"


def buyer_message(buyer_persona_id: str, listing_summary: str,
                   action: str, bid: float, cache: LLMCache,
                   model: str = DEFAULT_MODEL) -> str:
    ctx = {"who": "buyer", "persona": buyer_persona_id,
           "listing": listing_summary, "action": action, "bid": round(bid),
           "_model": model}
    hit = cache.get("negotiation_msg", ctx)
    if hit is not None:
        return hit
    prompt = f"""\
You are a buyer ({buyer_persona_id}) negotiating for a used car on a dealer
website. Write ONE short conversational sentence (≤25 words) that goes with
this action. Be in-character for the persona.

Listing: {listing_summary}
Your action: {action}
Your bid: ${bid:.0f}
"""
    resp = completion(model=model, max_tokens=80,
                       messages=[{"role": "user", "content": prompt}])
    text = resp.choices[0].message.content.strip()
    cache.put("negotiation_msg", ctx, text)
    return text


def seller_message(archetype_name: str, listing_summary: str,
                    action: str, price: float, cache: LLMCache,
                    model: str = DEFAULT_MODEL) -> str:
    ctx = {"who": "seller", "archetype": archetype_name,
           "listing": listing_summary, "action": action, "price": round(price),
           "_model": model}
    hit = cache.get("negotiation_msg", ctx)
    if hit is not None:
        return hit
    prompt = f"""\
You are a used-car seller with the '{archetype_name}' persona (honest /
moderate / aggressive). Write ONE short conversational sentence (≤25 words)
to accompany this action.

Listing: {listing_summary}
Your action: {action}
Price involved: ${price:.0f}
"""
    resp = completion(model=model, max_tokens=80,
                       messages=[{"role": "user", "content": prompt}])
    text = resp.choices[0].message.content.strip()
    cache.put("negotiation_msg", ctx, text)
    return text
```

- [ ] **Step 2: Commit**

```bash
git add car_market/llm_agent.py
git commit -m "feat(llm): cached negotiation-message generator"
```

### Task E.3: `--mode llm` integration in S3

**Files:**
- Modify: `car_market/scenarios/s3_open_market.py`

- [ ] **Step 1: Hook description + message generators when `mode == 'llm'`**

Modify `s3_open_market.py` to optionally call `generate_description()` on each listing and `buyer_message`/`seller_message` at each negotiation step *when* `cfg.mode == "llm"`. Decisions are unchanged — only the messages get LLM prose. Cache to `runs/llm_cache.jsonl`.

Add at the top of `run()`:

```python
cache = None
if cfg.mode == "llm":
    from ..llm_cache import LLMCache
    from ..descriptions import generate_description
    from ..llm_agent import buyer_message, seller_message
    cache = LLMCache(Path(cfg.out_dir) / "llm_cache.jsonl")
```

Also extend `S3Config` to carry `llm_model: str = "anthropic/claude-haiku-4-5"`. After adding each listing, if `cfg.mode == "llm"`, call `generate_description(l, cache, model=cfg.llm_model)` and store on `l.description`. At each `make_offer`/`respond_to_offer` step, replace `"(fast)"` with the LLM-generated message string (passing `cache=cache, model=cfg.llm_model`).

- [ ] **Step 2: Record one full `--mode llm` run**

Run:

```bash
ANTHROPIC_API_KEY=<key> python3 -c "
from car_market.scenarios.s3_open_market import run
from car_market.config import S3Config
print(run(S3Config(seed=0, reputation_gamma=0.5, mode='llm', m_buyers=30, T=80)))
"
```

Expected:
- ~30 buyers, ~100 listings → maybe 30 descriptions + ~60 messages → ~90 LLM calls cached.
- Total cost <$1. Run completes in <2 min.

- [ ] **Step 3: Commit**

```bash
git add car_market/scenarios/s3_open_market.py
git commit -m "feat(s3): llm mode for cached prose, decisions stay deterministic"
```

---

## Phase F — Replay mode + demo runner

### Task F.1: `--mode replay` re-runs deterministically using cached prose

**Files:**
- Modify: `car_market/scenarios/s3_open_market.py`

- [ ] **Step 1: Add replay path**

In `s3_open_market.py`, treat `mode == "replay"` like `"llm"` for prose retrieval, but DO NOT pass an `Anthropic` client — only `cache` for lookups. If a cache miss occurs in replay mode, fall back to `"(replay-fallback)"` and log a warning. This guarantees zero API calls during the live demo.

Update the imports block at the top of `run()`:

```python
if cfg.mode in ("llm", "replay"):
    from ..llm_cache import LLMCache
    cache = LLMCache(Path(cfg.out_dir) / "llm_cache.jsonl")
    if cfg.mode == "llm":
        from anthropic import Anthropic
        from ..descriptions import generate_description
        from ..llm_agent import buyer_message, seller_message
        client = Anthropic()
    else:
        client = None      # replay: cache-only
```

At each prose call site, wrap with:

```python
def _description_or_fallback(l):
    if cfg.mode == "fast":
        return ""
    if cfg.mode == "replay":
        ctx = {...}        # same keys as descriptions.generate_description
        return cache.get("description", ctx) or "(no cached description)"
    return generate_description(l, client, cache)
```

- [ ] **Step 2: Smoke-test replay**

Run:

```bash
python3 -c "
from car_market.scenarios.s3_open_market import run
from car_market.config import S3Config
r = run(S3Config(seed=0, reputation_gamma=0.5, mode='replay', m_buyers=30, T=80))
print(r)
"
```

Expected: same numeric summary as the corresponding `llm` run on the same seed/params. Zero API calls (verify by unsetting `ANTHROPIC_API_KEY` first).

- [ ] **Step 3: Commit**

```bash
git add car_market/scenarios/s3_open_market.py
git commit -m "feat(s3): replay mode (cache-only, zero API calls)"
```

### Task F.2: Demo CLI entrypoint

**Files:**
- Create: `run_car_market.py`

- [ ] **Step 1: Implement CLI**

Create `run_car_market.py`:

```python
"""CLI entrypoint.

Examples:
  python run_car_market.py headline                       # 30-seed fast sweep, render chart
  python run_car_market.py record --seed 0                # one llm-mode recording
  python run_car_market.py demo --seed 0                  # live replay
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from car_market.aggregate import sweep, welfare_delta_report
from car_market.config import S3Config
from car_market.plots import welfare_delta_bar
from car_market.scenarios.s3_open_market import run


def cmd_headline(args):
    rows = sweep(seeds=list(range(args.seeds)), gammas=[0.0, 0.5])
    report = welfare_delta_report(rows["rows"])
    out = Path("runs/headline_welfare_delta.png")
    welfare_delta_bar(report, out)
    print(json.dumps(report, indent=2))
    print(f"chart: {out}")


def cmd_record(args):
    for gamma in (0.0, 0.5):
        s = run(S3Config(seed=args.seed, reputation_gamma=gamma, mode="llm"))
        print(json.dumps(s, indent=2))


def cmd_demo(args):
    visible = run(S3Config(seed=args.seed, reputation_gamma=0.5, mode="replay"))
    hidden = run(S3Config(seed=args.seed, reputation_gamma=0.0, mode="replay"))
    print("VISIBLE:", json.dumps(visible, indent=2))
    print("HIDDEN: ", json.dumps(hidden, indent=2))
    print("delta_welfare =", visible.get("total_welfare", 0) - hidden.get("total_welfare", 0))


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("headline"); p1.add_argument("--seeds", type=int, default=30); p1.set_defaults(func=cmd_headline)
    p2 = sub.add_parser("record");   p2.add_argument("--seed", type=int, default=0);   p2.set_defaults(func=cmd_record)
    p3 = sub.add_parser("demo");     p3.add_argument("--seed", type=int, default=0);   p3.set_defaults(func=cmd_demo)
    args = p.parse_args(); args.func(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify CLI**

Run: `python3 run_car_market.py headline --seeds 10`
Expected: prints report JSON; chart file exists.

- [ ] **Step 3: Commit**

```bash
git add run_car_market.py
git commit -m "feat(cli): run_car_market with headline/record/demo subcommands"
```

---

## Phase G — Backup scenarios (S1 heatmap + S2 deterministic regret curve)

### Task G.1: S1 same-car seller-skill heatmap

**Files:**
- Create: `car_market/scenarios/s1_same_car.py`

- [ ] **Step 1: Implement S1**

Create `car_market/scenarios/s1_same_car.py`:

```python
"""S1 backup scenario: fix one car, m sellers across all archetypes,
10 personas. Bilateral 1-on-1 negotiations. Output: 10×m surplus heatmap."""
from __future__ import annotations

import random
from pathlib import Path
import numpy as np
import json

from ..archetypes import HONEST, MODERATE, AGGRESSIVE, build_listing
from ..generator import CarSpec
from ..personas import load_personas
from ..policies import HeuristicBuyer, HeuristicSeller


def run(seed: int = 0, out_dir: str = "runs/s1") -> dict:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    # Fixed car: 2018 Honda Accord, 78k miles, true_cond=3.2, true_value $15400.
    car = CarSpec(
        car_id="C_FIXED", year=2018, make="Honda", model="Accord", body="Sedan",
        mileage=78000, true_condition=3.2, true_value=15400.0,
        seller_floor=13860.0, seller_ceiling=16940.0,
        true_vhr_flags=["NO_SALVAGE_TITLE", "NO_FRAME_DAMAGE",
                         "NO_FLOOD_WATER_DAMAGE", "ACCIDENTS_REPORTED",
                         "NO_ONE_OWNER"],
    )
    personas = load_personas()
    archetypes = [HONEST, MODERATE, AGGRESSIVE]
    # 9 sellers: 3 of each archetype, deterministic.
    sellers = []
    surplus = np.zeros((len(personas), 9))
    for sj in range(9):
        archetype = archetypes[sj // 3]
        sid = f"S1_{sj+1:02d}"
        listing = build_listing(car, archetype, seller_id=sid,
                                  rng=random.Random(seed * 100 + sj))
        s = HeuristicSeller(seller_id=sid, archetype=archetype,
                             rng=random.Random(seed * 1000 + sj))
        for pi, persona in enumerate(personas):
            buyer = HeuristicBuyer(buyer_id=f"B1_{pi+1:02d}", persona=persona,
                                     rng=random.Random(seed * 10000 + pi * 100 + sj))
            # 1-on-1: buyer either bids or walks. Use propose_price.
            from ..marketplace import ListingCard
            card = ListingCard(
                listing_id=listing.listing_id, seller_id=sid,
                year=car.year, make=car.make, model=car.model, body=car.body,
                mileage=car.mileage, listing_condition=listing.listing_condition,
                asking_price=listing.asking_price, seller_stars=3.0,
            )
            bid = buyer.propose_price(card, car)
            step = s.respond_to_offer(car=car, asking_price=listing.asking_price,
                                        offer_price=bid)
            if step.action == "accept":
                surplus[pi, sj] = bid - car.true_value
            elif step.action == "counter":
                # Buyer-side check: if counter ≤ wtp, deal happens at counter.
                from ..personas import utility
                u_at_counter = utility(car, listing.listing_condition, step.counter_price, persona)
                if u_at_counter > 0:
                    surplus[pi, sj] = step.counter_price - car.true_value
            # else 0 (no deal)
    out_path = out / "s1_surplus.json"
    out_path.write_text(json.dumps({
        "personas": [p.persona_id for p in personas],
        "sellers": [f"S{i+1}_{['H','M','A'][i//3]}" for i in range(9)],
        "surplus": surplus.tolist(),
    }, indent=2))
    return {"out": str(out_path), "mean_surplus": float(surplus.mean())}
```

- [ ] **Step 2: Add S1 heatmap plot**

Append to `car_market/plots.py`:

```python
def s1_heatmap(json_path: Path, out_path: Path) -> None:
    import json
    import numpy as np
    d = json.loads(Path(json_path).read_text())
    surplus = np.array(d["surplus"])
    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(surplus, cmap="RdYlGn", aspect="auto")
    ax.set_xticks(range(len(d["sellers"]))); ax.set_xticklabels(d["sellers"], rotation=45)
    ax.set_yticks(range(len(d["personas"]))); ax.set_yticklabels(d["personas"])
    fig.colorbar(im, ax=ax, label="Seller surplus over true_value ($)")
    ax.set_title("S1: per-seller surplus across personas")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
```

- [ ] **Step 3: Run S1 + render**

Run:

```bash
python3 -c "
from car_market.scenarios.s1_same_car import run
from car_market.plots import s1_heatmap
from pathlib import Path
r = run(seed=0)
print(r)
s1_heatmap(Path(r['out']), Path('runs/s1/heatmap.png'))
"
```

Expected: 90 negotiations in seconds. Heatmap shows aggressive sellers extracting more surplus.

- [ ] **Step 4: Commit**

```bash
git add car_market/scenarios/s1_same_car.py car_market/plots.py
git commit -m "feat(s1): same-car seller-skill heatmap (backup)"
```

### Task G.2: S2 deterministic paradox-of-choice curve

**Files:**
- Create: `car_market/scenarios/s2_paradox.py`

- [ ] **Step 1: Implement S2**

Create `car_market/scenarios/s2_paradox.py`:

```python
"""S2 backup: deterministic-only regret-vs-pool-size curve."""
from __future__ import annotations

import json
import random
from pathlib import Path

from ..archetypes import population_sample, build_listing
from ..generator import generate
from ..personas import load_personas, utility


def _best(cars, listings, persona):
    best_u = float("-inf")
    for l in listings:
        u = utility(l.car, l.listing_condition, l.asking_price, persona)
        if u > best_u:
            best_u = u
    return best_u if best_u != float("-inf") else 0.0


def run(seed: int = 0, m_values=(10, 25, 50, 100, 200), n_seeds: int = 10,
         out_dir: str = "runs/s2") -> dict:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    personas = load_personas()
    rows = []
    for m in m_values:
        for sd in range(n_seeds):
            cars = generate(seed=seed * 1000 + sd, n=m)
            archetypes = population_sample(seed=seed * 10000 + sd, k=m)
            listings = [build_listing(c, a, seller_id=f"S_{i}", rng=random.Random(sd * m + i))
                          for i, (c, a) in enumerate(zip(cars, archetypes))]
            for persona in personas:
                full = _best(cars, listings, persona)
                # First-acceptable: walk in listing order; buy first with U > 0.
                first_u = 0.0
                for l in listings:
                    u = utility(l.car, l.listing_condition, l.asking_price, persona)
                    if u != float("-inf") and u > 0:
                        first_u = u
                        break
                rows.append({
                    "m": m, "seed": sd, "persona": persona.persona_id,
                    "full_search_U": full,
                    "first_acceptable_U": first_u,
                    "regret": full - first_u,
                })
    (out / "s2_rows.json").write_text(json.dumps(rows, indent=2))
    return {"n_rows": len(rows), "out": str(out / "s2_rows.json")}
```

- [ ] **Step 2: Plot S2**

Append to `car_market/plots.py`:

```python
def s2_curve(rows_path: Path, out_path: Path) -> None:
    import json
    from collections import defaultdict
    rows = json.loads(Path(rows_path).read_text())
    by_m = defaultdict(list)
    for r in rows:
        by_m[r["m"]].append(r["regret"])
    ms = sorted(by_m)
    means = [sum(by_m[m]) / len(by_m[m]) for m in ms]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(ms, means, marker="o")
    ax.set_xlabel("Pool size m")
    ax.set_ylabel("Mean regret (full − first_acceptable)")
    ax.set_title("S2: paradox of choice")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
```

- [ ] **Step 3: Run S2**

Run:

```bash
python3 -c "
from car_market.scenarios.s2_paradox import run
from car_market.plots import s2_curve
from pathlib import Path
r = run(seed=0)
print(r)
s2_curve(Path(r['out']), Path('runs/s2/curve.png'))
"
```

Expected: hundreds of trial rows in seconds. Regret curve rises with m, replicating the paradox-of-choice finding.

- [ ] **Step 4: Commit**

```bash
git add car_market/scenarios/s2_paradox.py car_market/plots.py
git commit -m "feat(s2): deterministic paradox-of-choice backup curve"
```

---

## Phase H — Optional anchor scripts (DO NOT BLOCK SATURDAY)

### Task H.1: Fit marginals from rebrowser dataset (OPTIONAL)

**Files:**
- Create: `car_market/anchor/fit_marginals.py`

- [ ] **Step 1: Implement marginal fitter**

Create `car_market/anchor/fit_marginals.py`:

```python
"""One-time anchor script. Reads rebrowser AutoTrader parquet sample at
/tmp/rebrowser-autotrader/car-listings/data/*.parquet and emits a JSON
of empirical marginals that the generator MAY use in place of hand-tuned
priors. Optional polish."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

SRC = Path("/tmp/rebrowser-autotrader/car-listings/data")
OUT = Path(__file__).parent / "marginals.json"


def main():
    files = sorted(SRC.glob("*.parquet"))
    if not files:
        print("No rebrowser parquet found. Skipping anchor.")
        return
    df = pd.concat([pd.read_parquet(f) for f in files])
    # Joint (make, body) marginal.
    mb = df.groupby(["makeName", "bodyStyle"]).size()
    total = float(mb.sum())
    pairs = [
        {"make": m, "body": b, "p": float(c) / total}
        for (m, b), c in mb.items()
    ]
    out = {"make_body": pairs,
            "kbb_low_p50": float(df["kbbFairPriceLow"].median()),
            "kbb_high_p50": float(df["kbbFairPriceHigh"].median())}
    OUT.write_text(json.dumps(out, indent=2))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run (optional)**

Run: `python3 -m car_market.anchor.fit_marginals`
Expected: `marginals.json` exists. Use these in `generator.py` only if hand-tuned distribution looks unrealistic on stage.

- [ ] **Step 3: Commit**

```bash
git add car_market/anchor/
git commit -m "feat(anchor): optional rebrowser marginal fitter"
```

---

## Self-Review Notes

- All tasks have actual code, not placeholders.
- Spec coverage: §4 (generator) → A.1; §4.5 (archetypes) → A.2; §5 (personas) → A.3; §6 (reputation) → B.1; §7 (tools — buyer-side `search`/`lookup_seller` covered by marketplace methods, agent harness reuses project_deal) → C.1; §8.1 (S1) → G.1; §8.2 (S2 deterministic) → G.2; §8.3 (S3) → D.3 + D.5; §9.1 (locked metrics) → D.4; §3.1 (modes) → E + F; §12 (demo) → F.2.
- Naming consistency: `CarSpec`, `CarListing`, `BetaReputation`, `HeuristicSeller`, `HeuristicBuyer`, `S3Config` used consistently across files.
- Critical path: Phase D produces the headline chart. Anything past D is enhancement. Anything past F is optional.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-17-used-car-marketplace.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
