"""Config and options flow of the Therma V Carnot integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import (
    BASIS_REFRIGERANT,
    BASIS_TEMPERATURES,
    BASIS_WATER,
    CONF_AUX_POWER,
    CONF_BASIS,
    CONF_DEFROST,
    CONF_DELTA_T_HIGH,
    CONF_DELTA_T_LOW,
    CONF_EFFICIENCY_HIGH,
    CONF_EFFICIENCY_LOW,
    CONF_FLOW_TEMP,
    CONF_POWER,
    CONF_RETURN_TEMP,
    CONF_RUNNING,
    DOMAIN,
    SUGGESTED_SUFFIXES,
)
from .model import Constants


def _suggest(hass: HomeAssistant, key: str) -> str | None:
    """Entity ID of the firmware entity for this source, if exactly one exists."""
    domain, suffix = SUGGESTED_SUFFIXES[key]
    hits = [e for e in hass.states.async_entity_ids(domain) if e.endswith(suffix)]
    return hits[0] if len(hits) == 1 else None


def _entity_field(hass: HomeAssistant, key: str, required: bool) -> tuple[Any, Any]:
    domain = SUGGESTED_SUFFIXES[key][0]
    suggested = _suggest(hass, key)
    marker = vol.Required if required else vol.Optional
    field = marker(key, description={"suggested_value": suggested} if suggested else None)
    return field, selector.EntitySelector(selector.EntitySelectorConfig(domain=domain))


def _number(minimum: float, maximum: float, step: float, unit: str | None = None) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=minimum, max=maximum, step=step, unit_of_measurement=unit,
            mode=selector.NumberSelectorMode.BOX,
        )
    )


def constants_schema(values: dict[str, Any]) -> vol.Schema:
    """Schema of the calibration constants, prefilled with ``values``."""
    d = Constants()
    return vol.Schema(
        {
            vol.Required(CONF_EFFICIENCY_LOW, default=values.get(CONF_EFFICIENCY_LOW, d.efficiency_low * 100)): _number(1, 100, 0.5, "%"),
            vol.Required(CONF_EFFICIENCY_HIGH, default=values.get(CONF_EFFICIENCY_HIGH, d.efficiency_high * 100)): _number(1, 100, 0.5, "%"),
            vol.Required(CONF_DELTA_T_LOW, default=values.get(CONF_DELTA_T_LOW, d.delta_t_low)): _number(0, 20, 0.1, "K"),
            vol.Required(CONF_DELTA_T_HIGH, default=values.get(CONF_DELTA_T_HIGH, d.delta_t_high)): _number(0, 20, 0.1, "K"),
            vol.Required(CONF_AUX_POWER, default=values.get(CONF_AUX_POWER, d.aux_power_w)): _number(0, 1000, 5, "W"),
        }
    )


class ThermaVCarnotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Two steps: temperature basis, then the source entities."""

    VERSION = 1

    def __init__(self) -> None:
        self._basis = BASIS_WATER

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._basis = user_input[CONF_BASIS]
            return await self.async_step_entities()
        schema = vol.Schema(
            {
                vol.Required(CONF_BASIS, default=BASIS_WATER): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[BASIS_WATER, BASIS_REFRIGERANT],
                        translation_key=CONF_BASIS,
                    )
                )
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_entities(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        warm, cold = BASIS_TEMPERATURES[self._basis]
        if user_input is not None:
            if user_input[CONF_FLOW_TEMP] == user_input[CONF_RETURN_TEMP]:
                errors["base"] = "same_water_entities"
            elif user_input[warm] == user_input[cold]:
                errors["base"] = "same_carnot_entities"
            else:
                return self.async_create_entry(
                    title="Therma V Carnot",
                    data={CONF_BASIS: self._basis, **user_input},
                )
        keys = [(warm, True), (cold, True), (CONF_FLOW_TEMP, True), (CONF_RETURN_TEMP, True),
                (CONF_POWER, True), (CONF_RUNNING, True), (CONF_DEFROST, False)]
        fields: dict[Any, Any] = {}
        for key, required in dict.fromkeys(keys):  # the flow temp is also the warm side (water)
            field, sel = _entity_field(self.hass, key, required)
            fields[field] = sel
        schema = vol.Schema(fields)
        if user_input is not None:  # keep the user's choice after an error
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(step_id="entities", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ThermaVCarnotOptionsFlow()


class ThermaVCarnotOptionsFlow(OptionsFlow):
    """Calibration constants."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_DELTA_T_LOW] >= user_input[CONF_DELTA_T_HIGH]:
                errors["base"] = "invalid_delta_t"
            else:
                return self.async_create_entry(data=user_input)
        values = user_input if user_input is not None else dict(self.config_entry.options)
        return self.async_show_form(step_id="init", data_schema=constants_schema(values), errors=errors)
