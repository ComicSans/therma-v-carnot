"""Carnot-based heat output model (pure functions, no Home Assistant imports).

The heat pump reports temperatures and electric power but no water flow rate,
so heat output and COP cannot be measured directly. This model estimates them
from the Carnot limit instead:

1. Carnot COP from a warm and a cold temperature (kelvin):
   ``cop_carnot = T_warm / (T_warm - T_cold)``.
2. Carnot efficiency (share of the Carnot limit the unit reaches), linear in
   the water delta T between two calibration points.
3. Estimated COP = efficiency x Carnot COP.
4. Heat output = COP x (electric power - auxiliary power).
5. Flow rate = heat output / (water heat capacity x delta T).

Model and default constants come from a community contribution, see
https://github.com/ComicSans/lg-therma-v-esphome-modbus/issues/17. The
constants were calibrated on one unit; treat every result as an estimate.
"""

from __future__ import annotations

from dataclasses import dataclass

KELVIN_OFFSET = 273.15

# Heat carried by water per L/min and kelvin, in watts:
# 4.18 kJ/(kg*K) * ~0.995 kg/L / 60 s/min = ~69.3 W per (L/min * K); the
# value 69.34 is the one used in issue 17.
WATER_W_PER_LPM_K = 69.34

# Below this temperature lift the Carnot COP is unbounded or meaningless.
MIN_LIFT_K = 1.0
# Below this water delta T the flow rate is not reported (division by ~0).
MIN_FLOW_DELTA_T_K = 0.5


@dataclass(frozen=True)
class Constants:
    """Calibration constants of the model."""

    efficiency_low: float = 0.40  # Carnot efficiency at delta T <= delta_t_low
    efficiency_high: float = 0.55  # Carnot efficiency at delta T >= delta_t_high
    delta_t_low: float = 2.0  # K
    delta_t_high: float = 5.0  # K
    aux_power_w: float = 100.0  # controller, inverter losses, pump, fan


@dataclass(frozen=True)
class Inputs:
    """One set of source values. Temperatures in degrees Celsius, power in W."""

    warm_c: float | None
    cold_c: float | None
    flow_c: float | None
    return_c: float | None
    power_w: float | None
    running: bool | None  # None: source unavailable
    defrosting: bool | None  # None: source unavailable or not configured


@dataclass(frozen=True)
class Result:
    """Model output; None where a value cannot be computed."""

    carnot_cop: float | None
    efficiency: float | None
    cop: float | None
    heat_output_w: float | None
    flow_rate_lpm: float | None


def carnot_cop(warm_c: float, cold_c: float) -> float | None:
    """Carnot COP for heating between two temperatures in degrees Celsius."""
    lift = warm_c - cold_c
    if lift < MIN_LIFT_K:
        return None
    return (warm_c + KELVIN_OFFSET) / lift


def carnot_efficiency(delta_t: float, c: Constants) -> float:
    """Share of the Carnot limit, linear in delta T between the two points."""
    if c.delta_t_high <= c.delta_t_low:
        # Degenerate calibration: a step at delta_t_low.
        return c.efficiency_high if delta_t >= c.delta_t_low else c.efficiency_low
    if delta_t <= c.delta_t_low:
        return c.efficiency_low
    if delta_t >= c.delta_t_high:
        return c.efficiency_high
    share = (delta_t - c.delta_t_low) / (c.delta_t_high - c.delta_t_low)
    return c.efficiency_low + share * (c.efficiency_high - c.efficiency_low)


def evaluate(i: Inputs, c: Constants) -> Result:
    """Evaluate the model for one set of inputs."""
    cop_c = None
    if i.warm_c is not None and i.cold_c is not None:
        cop_c = carnot_cop(i.warm_c, i.cold_c)

    delta_t = None
    if i.flow_c is not None and i.return_c is not None:
        delta_t = i.flow_c - i.return_c

    eff = carnot_efficiency(delta_t, c) if delta_t is not None else None
    cop = eff * cop_c if eff is not None and cop_c is not None else None

    # Heat output: zero while the compressor stands or the unit defrosts (the
    # model has no sign for the heat taken from the water during a defrost).
    # COP and flow rate are undefined then. An unavailable compressor signal
    # makes the heat output unknown, so the energy sum skips that interval.
    if i.running is False or i.defrosting is True:
        return Result(cop_c, eff, None, 0.0, None)
    if i.running is None:
        return Result(cop_c, eff, None, None, None)
    if cop is None or i.power_w is None:
        return Result(cop_c, eff, cop, None, None)

    heat = cop * max(i.power_w - c.aux_power_w, 0.0)
    flow = None
    if delta_t is not None and delta_t >= MIN_FLOW_DELTA_T_K:
        flow = heat / (WATER_W_PER_LPM_K * delta_t)
    return Result(cop_c, eff, cop, heat, flow)
