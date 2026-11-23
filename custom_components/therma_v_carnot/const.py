"""Constants of the Therma V Carnot integration."""

from __future__ import annotations

DOMAIN = "therma_v_carnot"

CONF_BASIS = "basis"
BASIS_WATER = "water"
BASIS_REFRIGERANT = "refrigerant"

# Source entities.
CONF_FLOW_TEMP = "flow_temperature"
CONF_RETURN_TEMP = "return_temperature"
CONF_OUTDOOR_TEMP = "outdoor_temperature"
CONF_CONDENSING_TEMP = "condensing_temperature"
CONF_EVAPORATING_TEMP = "evaporating_temperature"
CONF_POWER = "power"
CONF_RUNNING = "compressor_running"
CONF_DEFROST = "defrost"

# Calibration constants (options).
CONF_EFFICIENCY_LOW = "efficiency_low"
CONF_EFFICIENCY_HIGH = "efficiency_high"
CONF_DELTA_T_LOW = "delta_t_low"
CONF_DELTA_T_HIGH = "delta_t_high"
CONF_AUX_POWER = "aux_power"

# Entity ID suffixes of the lg-therma-v-esphome-modbus firmware, used to
# suggest the source entities in the config flow.
SUGGESTED_SUFFIXES: dict[str, tuple[str, str]] = {
    CONF_FLOW_TEMP: ("sensor", "_water_flow_temperature"),
    CONF_RETURN_TEMP: ("sensor", "_water_return_temperature"),
    CONF_OUTDOOR_TEMP: ("sensor", "_outdoor_temperature_unit_sensor"),
    CONF_CONDENSING_TEMP: ("sensor", "_condensing_temperature"),
    CONF_EVAPORATING_TEMP: ("sensor", "_evaporating_temperature"),
    CONF_POWER: ("sensor", "_active_power_measured"),
    CONF_RUNNING: ("binary_sensor", "_compressor_running"),
    CONF_DEFROST: ("binary_sensor", "_defrost_active"),
}

# Warm and cold side of the Carnot limit per basis.
BASIS_TEMPERATURES: dict[str, tuple[str, str]] = {
    BASIS_WATER: (CONF_FLOW_TEMP, CONF_OUTDOOR_TEMP),
    BASIS_REFRIGERANT: (CONF_CONDENSING_TEMP, CONF_EVAPORATING_TEMP),
}

# Gaps longer than this are not integrated into the heat energy (restart,
# unavailable sources).
MAX_INTEGRATION_GAP_S = 600
UPDATE_INTERVAL_S = 60
