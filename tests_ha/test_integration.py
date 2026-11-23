"""Config flow, options flow and sensors in a real Home Assistant."""


from datetime import timedelta
import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

D = "therma_v_carnot"
P = "heizungskeller_warmepumpe_modbus"

def seed(hass, flow=35.0, ret=30.0, out=5.0, cond=40.0, evap=-2.0, power=1100, running="on", defrost="off"):
    hass.states.async_set(f"sensor.{P}_water_flow_temperature", flow, {"unit_of_measurement": "°C"})
    hass.states.async_set(f"sensor.{P}_water_return_temperature", ret, {"unit_of_measurement": "°C"})
    hass.states.async_set(f"sensor.{P}_outdoor_temperature_unit_sensor", out, {"unit_of_measurement": "°C"})
    hass.states.async_set(f"sensor.{P}_condensing_temperature", cond, {"unit_of_measurement": "°C"})
    hass.states.async_set(f"sensor.{P}_evaporating_temperature", evap, {"unit_of_measurement": "°C"})
    hass.states.async_set(f"sensor.{P}_active_power_measured", power, {"unit_of_measurement": "W"})
    hass.states.async_set(f"binary_sensor.{P}_compressor_running", running)
    hass.states.async_set(f"binary_sensor.{P}_defrost_active", defrost)

async def setup(hass, basis):
    seed(hass)
    r = await hass.config_entries.flow.async_init(D, context={"source": config_entries.SOURCE_USER})
    assert r["type"] == FlowResultType.FORM and r["step_id"] == "user"
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"basis": basis})
    assert r["step_id"] == "entities"
    keys = [str(k) for k in r["data_schema"].schema]
    # suggested values from the firmware suffixes
    sugg = {str(k): k.description["suggested_value"] for k in r["data_schema"].schema if k.description}
    assert len(sugg) == len(keys), (keys, sugg)
    r = await hass.config_entries.flow.async_configure(r["flow_id"], sugg)
    assert r["type"] == FlowResultType.CREATE_ENTRY, r
    await hass.async_block_till_done()
    return r["result"], keys

def val(hass, key):
    s = [x for x in hass.states.async_all("sensor") if x.entity_id.startswith("sensor.therma_v_carnot") and x.entity_id.endswith(key)]
    assert len(s) == 1, [x.entity_id for x in hass.states.async_all("sensor")]
    return s[0].state

async def test_water(hass):
    entry, keys = await setup(hass, "water")
    assert "condensing_temperature" not in keys and len(keys) == 6  # flow is the warm side
    assert float(val(hass, "carnot_cop")) == pytest.approx(308.15 / 30, rel=1e-3)
    assert float(val(hass, "estimated_cop")) == pytest.approx(0.55 * 308.15 / 30, rel=1e-3)
    assert float(val(hass, "estimated_heat_output")) == pytest.approx(0.55 * 308.15 / 30 * 1000, rel=1e-3)
    assert float(val(hass, "estimated_flow_rate")) > 0
    assert float(val(hass, "carnot_efficiency")) == pytest.approx(55.0)
    # defrost -> 0 W, cop unknown
    hass.states.async_set(f"binary_sensor.{P}_defrost_active", "on")
    await hass.async_block_till_done()
    assert float(val(hass, "estimated_heat_output")) == 0
    assert val(hass, "estimated_cop") == "unknown"
    # energy integrates over time
    hass.states.async_set(f"binary_sensor.{P}_defrost_active", "off")
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
    await hass.async_block_till_done()
    assert float(val(hass, "estimated_heat_energy")) >= 0
    # options flow
    r = await hass.config_entries.options.async_init(entry.entry_id)
    assert r["step_id"] == "init"
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"efficiency_low": 40, "efficiency_high": 60, "delta_t_low": 2, "delta_t_high": 5, "aux_power": 100})
    assert r["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert float(val(hass, "carnot_efficiency")) == pytest.approx(60.0)
    assert await hass.config_entries.async_unload(entry.entry_id)

async def test_refrigerant(hass):
    entry, keys = await setup(hass, "refrigerant")
    assert "outdoor_temperature" not in keys and "condensing_temperature" in keys
    assert float(val(hass, "carnot_cop")) == pytest.approx(313.15 / 42, rel=1e-3)

async def test_same_entities_error(hass):
    seed(hass)
    r = await hass.config_entries.flow.async_init(D, context={"source": config_entries.SOURCE_USER})
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"basis": "water"})
    f = f"sensor.{P}_water_flow_temperature"
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {
        "flow_temperature": f, "return_temperature": f, "outdoor_temperature": f"sensor.{P}_outdoor_temperature_unit_sensor",
        "power": f"sensor.{P}_active_power_measured", "compressor_running": f"binary_sensor.{P}_compressor_running"})
    assert r["errors"] == {"base": "same_water_entities"}


async def test_unavailable_running_gives_unknown_heat(hass):
    await setup(hass, "water")
    hass.states.async_set(f"binary_sensor.{P}_compressor_running", "unavailable")
    await hass.async_block_till_done()
    assert val(hass, "estimated_heat_output") == "unknown"


async def test_units_are_converted(hass):
    await setup(hass, "water")
    hass.states.async_set(f"sensor.{P}_active_power_measured", 1.1, {"unit_of_measurement": "kW"})
    hass.states.async_set(f"sensor.{P}_outdoor_temperature_unit_sensor", 41.0, {"unit_of_measurement": "°F"})
    await hass.async_block_till_done()
    assert float(val(hass, "carnot_cop")) == pytest.approx(308.15 / 30, rel=1e-3)
    assert float(val(hass, "estimated_heat_output")) == pytest.approx(0.55 * 308.15 / 30 * 1000, rel=1e-3)


async def test_options_reject_inverted_delta_t(hass):
    entry, _ = await setup(hass, "water")
    r = await hass.config_entries.options.async_init(entry.entry_id)
    r = await hass.config_entries.options.async_configure(r["flow_id"], {
        "efficiency_low": 40, "efficiency_high": 55, "delta_t_low": 5, "delta_t_high": 2, "aux_power": 100})
    assert r["errors"] == {"base": "invalid_delta_t"}


async def test_heat_energy_accumulates(hass, freezer):
    await setup(hass, "water")
    start = float(val(hass, "estimated_heat_energy"))
    freezer.tick(timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    heat_w = 0.55 * 308.15 / 30 * 1000
    assert float(val(hass, "estimated_heat_energy")) - start == pytest.approx(heat_w * 120 / 3_600_000, rel=0.02)
