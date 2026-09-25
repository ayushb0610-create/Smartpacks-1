"""
Unit tests for app/engine.py.

These use plain namespace objects instead of ORM instances so the tests
run with zero dependencies beyond the engine module itself (no DB, no
FastAPI, no network) — `python -m pytest tests/test_engine.py` or even
`python tests/test_engine.py` directly.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import engine  # noqa: E402


def make_commodity(**kw):
    defaults = dict(
        name="Apple", fat_pct=0.2, moisture_pct=86, ph=3.65,
        respiration_rate=4.7, o2_target_pct=3, co2_target_pct=2.5,
        base_shelf_life_days=20,
        respiration_curve=[[0, 1.5], [5, 3.1], [10, 4.7], [15, 8.1], [20, 11.1]],
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def make_material(**kw):
    defaults = dict(
        id=1, name="LDPE", bis_standard="IS 10146", otr=6500, wvtr=18,
        thickness_um=50, cost_index=1, sustainability=5, strength=5,
        sealability=9, light_barrier=3, temp_min_c=-50, temp_max_c=80,
        recyclable="Yes (#4)", note="cheap",
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def test_resp_at_uses_curve_interpolation():
    c = make_commodity()
    # Exact points on the curve should come back unchanged.
    assert engine.resp_at(c, 10) == 4.7
    assert engine.resp_at(c, 0) == 1.5
    # Midpoint should linearly interpolate between (5, 3.1) and (10, 4.7).
    mid = engine.resp_at(c, 7.5)
    assert 3.1 < mid < 4.7


def test_resp_at_falls_back_to_q10_without_curve():
    c = make_commodity(respiration_curve=None, respiration_rate=10)
    assert engine.resp_at(c, 10) == 10  # reference temp itself
    assert engine.resp_at(c, 20) > engine.resp_at(c, 10)  # warmer -> faster


def test_required_produce_scales_with_weight():
    c = make_commodity()
    small = engine.required(c, temp_c=4, weight_g=100, life_days=10, rh_pct=90, water_activity=0.97, ox_sensitivity=2)
    large = engine.required(c, temp_c=4, weight_g=1000, life_days=10, rh_pct=90, water_activity=0.97, ox_sensitivity=2)
    assert small.produce is True
    assert small.otr != large.otr  # area scales non-linearly with weight


def test_required_non_produce_uses_fat_and_moisture():
    c = make_commodity(respiration_rate=0, fat_pct=35, moisture_pct=2)
    req = engine.required(c, temp_c=25, weight_g=200, life_days=90, rh_pct=40, water_activity=0.15, ox_sensitivity=2)
    assert req.produce is False
    assert req.otr > 0
    assert req.wvtr > 0


def test_score_rejects_material_outside_temp_range():
    c = make_commodity()
    m = make_material(temp_min_c=10, temp_max_c=40)  # can't handle 4C chilled storage
    req = engine.required(c, temp_c=4, weight_g=500, life_days=10, rh_pct=90, water_activity=0.97, ox_sensitivity=2)
    assert engine.score(m, req, temp_c=4, priority="balanced", transport_severity=2, light_sensitivity=2) is None


def test_score_rewards_bis_standard():
    c = make_commodity()
    req = engine.required(c, temp_c=4, weight_g=500, life_days=10, rh_pct=90, water_activity=0.97, ox_sensitivity=2)
    with_bis = make_material(bis_standard="IS 10146")
    without_bis = make_material(bis_standard=None)
    s1 = engine.score(with_bis, req, 4, "balanced", 2, 2)
    s2 = engine.score(without_bis, req, 4, "balanced", 2, 2)
    assert s1["score"] > s2["score"]

    fit_otr = s1["fit"]["otr"]
    assert isinstance(fit_otr, int)


def test_shelf_life_is_at_least_one_day():
    c = make_commodity(base_shelf_life_days=0.01)
    m = make_material()
    req = engine.required(c, 40, 500, 1, 90, 0.97, 2)
    assert engine.shelf_life_days(c, m, 40, req) >= 1


def test_haversine_known_distance():
    # Mumbai -> New Delhi, roughly 1150-1160 km great-circle.
    km = engine.haversine_km(19.076, 72.877, 28.613, 77.209)
    assert 1100 < km < 1200


def test_js_round_matches_js_semantics():
    assert engine.js_round(2.5) == 3
    assert engine.js_round(-2.5) == -2
    assert engine.js_round(2.4) == 2


def test_rank_materials_sorted_best_first():
    c = make_commodity()
    materials = [
        make_material(id=1, name="LDPE", otr=6500, wvtr=18),
        make_material(id=2, name="Metallized PET/PE", otr=0.77, wvtr=1, strength=8),
    ]
    req, results = engine.rank_materials(
        c, materials, temp_c=4, weight_g=500, life_days=10, rh_pct=92,
        water_activity=0.97, ox_sensitivity=2, light_sensitivity=2,
        priority="balanced", transport_severity=2, ph_override=3.65,
    )
    assert req.ph == 3.65
    assert len(results) == 2
    assert results[0]["score"] >= results[1]["score"]


if __name__ == "__main__":
    failures = 0
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    if failures:
        raise SystemExit(1)
