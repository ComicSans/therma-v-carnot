"""Tests of the pure Carnot model."""

from __future__ import annotations

import pytest

from therma_v_carnot.model import (
    WATER_W_PER_LPM_K,
    Constants,
    Inputs,
    carnot_cop,
    carnot_efficiency,
    evaluate,
)

C = Constants()


def inputs(**kw):
    base = dict(warm_c=35.0, cold_c=5.0, flow_c=35.0, return_c=30.0,
                power_w=1100.0, running=True, defrosting=False)
    base.update(kw)
    return Inputs(**base)


def test_carnot_cop_kelvin():
    assert carnot_cop(35.0, 5.0) == pytest.approx(308.15 / 30.0)


@pytest.mark.parametrize("warm,cold", [(5.0, 5.0), (5.5, 5.0), (0.0, 10.0)])
def test_carnot_cop_needs_lift(warm, cold):
    assert carnot_cop(warm, cold) is None


@pytest.mark.parametrize(
    "delta_t,expected",
    [(0.0, 0.40), (2.0, 0.40), (3.0, 0.45), (4.0, 0.50), (5.0, 0.55), (9.0, 0.55)],
)
def test_efficiency_matches_issue_17(delta_t, expected):
    # Issue 17: 0.40 below 2 K, 0.55 above 5 K, 0.05 * delta T + 0.30 between.
    assert carnot_efficiency(delta_t, C) == pytest.approx(expected)


def test_efficiency_degenerate_calibration_is_a_step():
    c = Constants(delta_t_low=3.0, delta_t_high=3.0)
    assert carnot_efficiency(2.9, c) == c.efficiency_low
    assert carnot_efficiency(3.0, c) == c.efficiency_high


def test_full_chain():
    r = evaluate(inputs(), C)
    cop = 0.55 * 308.15 / 30.0
    assert r.cop == pytest.approx(cop)
    assert r.heat_output_w == pytest.approx(cop * 1000.0)
    assert r.flow_rate_lpm == pytest.approx(cop * 1000.0 / (WATER_W_PER_LPM_K * 5.0))


def test_flow_rate_constant_matches_issue_17():
    # Issue 17 divides kW by 0.06934 * delta T; same constant in watts.
    assert WATER_W_PER_LPM_K == pytest.approx(0.06934 * 1000)


@pytest.mark.parametrize("kw", [dict(running=False), dict(defrosting=True)])
def test_no_heat_when_stopped_or_defrosting(kw):
    r = evaluate(inputs(**kw), C)
    assert r.heat_output_w == 0.0
    assert r.cop is None
    assert r.flow_rate_lpm is None
    assert r.carnot_cop is not None


def test_aux_power_never_makes_heat_negative():
    assert evaluate(inputs(power_w=50.0), C).heat_output_w == 0.0


def test_missing_sources_give_none():
    r = evaluate(inputs(power_w=None), C)
    assert r.cop is not None and r.heat_output_w is None
    r = evaluate(inputs(cold_c=None), C)
    assert r.carnot_cop is None and r.cop is None and r.heat_output_w is None
    r = evaluate(inputs(return_c=None), C)
    assert r.efficiency is None and r.heat_output_w is None


def test_small_delta_t_gives_no_flow_rate():
    r = evaluate(inputs(return_c=34.8), C)
    assert r.heat_output_w > 0
    assert r.flow_rate_lpm is None


def test_refrigerant_basis_uses_given_temperatures():
    # Basis selection happens in the HA layer: the model only sees warm/cold.
    r = evaluate(inputs(warm_c=40.0, cold_c=-2.0), C)
    assert r.carnot_cop == pytest.approx(313.15 / 42.0)


def test_unavailable_compressor_signal_gives_unknown_heat():
    r = evaluate(inputs(running=None), C)
    assert r.heat_output_w is None and r.cop is None and r.flow_rate_lpm is None


def test_unavailable_defrost_signal_does_not_block():
    # running known, defrost unknown: estimate as normal operation.
    assert evaluate(inputs(defrosting=None), C).heat_output_w > 0
