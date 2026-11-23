"""Sensors of the Therma V Carnot integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    STATE_OFF,
    STATE_ON,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import (
    BASIS_TEMPERATURES,
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
    MAX_INTEGRATION_GAP_S,
    UPDATE_INTERVAL_S,
)
from .model import Constants, Inputs, Result, evaluate


@dataclass(frozen=True, kw_only=True)
class CarnotSensorDescription(SensorEntityDescription):
    """Sensor description with the function that picks the value."""

    value: Callable[[Result], float | None]


DESCRIPTIONS: tuple[CarnotSensorDescription, ...] = (
    CarnotSensorDescription(
        key="carnot_cop", translation_key="carnot_cop",
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=2,
        value=lambda r: r.carnot_cop,
    ),
    CarnotSensorDescription(
        key="carnot_efficiency", translation_key="carnot_efficiency",
        native_unit_of_measurement=PERCENTAGE, state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value=lambda r: None if r.efficiency is None else r.efficiency * 100,
    ),
    CarnotSensorDescription(
        key="cop", translation_key="cop",
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=2,
        value=lambda r: r.cop,
    ),
    CarnotSensorDescription(
        key="heat_output", translation_key="heat_output",
        native_unit_of_measurement=UnitOfPower.WATT, device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0,
        value=lambda r: r.heat_output_w,
    ),
    CarnotSensorDescription(
        key="flow_rate", translation_key="flow_rate",
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1,
        value=lambda r: r.flow_rate_lpm,
    ),
)


def _float(state: State | None) -> float | None:
    if state is None:
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


def _celsius(state: State | None) -> float | None:
    value = _float(state)
    unit = state.attributes.get("unit_of_measurement") if state else None
    if value is None or unit in (None, UnitOfTemperature.CELSIUS):
        return value
    if unit in (UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.KELVIN):
        return TemperatureConverter.convert(value, unit, UnitOfTemperature.CELSIUS)
    return None


def _watts(state: State | None) -> float | None:
    value = _float(state)
    unit = state.attributes.get("unit_of_measurement") if state else None
    if value is None or unit in (None, UnitOfPower.WATT):
        return value
    if unit == UnitOfPower.KILO_WATT:
        return value * 1000
    return None


def _on_off(state: State | None) -> bool | None:
    """True/False for on/off, None for a missing, unknown or unavailable source."""
    if state is None or state.state not in (STATE_ON, STATE_OFF):
        return None
    return state.state == STATE_ON


def constants_from_options(options: dict[str, Any]) -> Constants:
    d = Constants()
    return Constants(
        efficiency_low=options.get(CONF_EFFICIENCY_LOW, d.efficiency_low * 100) / 100,
        efficiency_high=options.get(CONF_EFFICIENCY_HIGH, d.efficiency_high * 100) / 100,
        delta_t_low=options.get(CONF_DELTA_T_LOW, d.delta_t_low),
        delta_t_high=options.get(CONF_DELTA_T_HIGH, d.delta_t_high),
        aux_power_w=options.get(CONF_AUX_POWER, d.aux_power_w),
    )


class CarnotHub:
    """Reads the source entities, evaluates the model and notifies the sensors."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.data = dict(entry.data)
        self.constants = constants_from_options(dict(entry.options))
        self.result = Result(None, None, None, None, None)
        self._listeners: list[Callable[[], None]] = []

    @property
    def sources(self) -> list[str]:
        return [v for k, v in self.data.items() if k != CONF_BASIS and v]

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def _state(self, key: str) -> State | None:
        entity_id = self.data.get(key)
        return self.hass.states.get(entity_id) if entity_id else None

    @callback
    def update(self, *_: Any) -> None:
        warm, cold = BASIS_TEMPERATURES[self.data[CONF_BASIS]]
        # Without a configured defrost entity the unit counts as not defrosting.
        defrosting = _on_off(self._state(CONF_DEFROST)) if self.data.get(CONF_DEFROST) else False
        inputs = Inputs(
            warm_c=_celsius(self._state(warm)),
            cold_c=_celsius(self._state(cold)),
            flow_c=_celsius(self._state(CONF_FLOW_TEMP)),
            return_c=_celsius(self._state(CONF_RETURN_TEMP)),
            power_w=_watts(self._state(CONF_POWER)),
            running=_on_off(self._state(CONF_RUNNING)),
            defrosting=defrosting,
        )
        self.result = evaluate(inputs, self.constants)
        for listener in list(self._listeners):
            listener()


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    hub = CarnotHub(hass, entry)
    device = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Therma V Carnot",
        manufacturer="Therma V Carnot",
        model=f"Carnot model ({entry.data[CONF_BASIS]} temperatures)",
        entry_type=DeviceEntryType.SERVICE,
    )
    entities: list[SensorEntity] = [CarnotSensor(hub, entry, device, d) for d in DESCRIPTIONS]
    entities.append(HeatEnergySensor(hub, entry, device))
    async_add_entities(entities)

    @callback
    def _on_change(_event: Event[EventStateChangedData]) -> None:
        hub.update()

    entry.async_on_unload(async_track_state_change_event(hass, hub.sources, _on_change))
    entry.async_on_unload(
        async_track_time_interval(hass, hub.update, timedelta(seconds=UPDATE_INTERVAL_S))
    )
    hub.update()


class _Base(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hub: CarnotHub, entry: ConfigEntry, device: DeviceInfo, key: str) -> None:
        self.hub = hub
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = device

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.hub.add_listener(self._on_update))
        self._on_update()

    @callback
    def _on_update(self) -> None:
        raise NotImplementedError


class CarnotSensor(_Base):
    """One value of the model result."""

    entity_description: CarnotSensorDescription

    def __init__(self, hub: CarnotHub, entry: ConfigEntry, device: DeviceInfo,
                 description: CarnotSensorDescription) -> None:
        super().__init__(hub, entry, device, description.key)
        self.entity_description = description

    @callback
    def _on_update(self) -> None:
        self._attr_native_value = self.entity_description.value(self.hub.result)
        self.async_write_ha_state()


class HeatEnergySensor(_Base, RestoreSensor):
    """Estimated heat energy: left Riemann sum of the estimated heat output."""

    _attr_translation_key = "heat_energy"
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 2

    def __init__(self, hub: CarnotHub, entry: ConfigEntry, device: DeviceInfo) -> None:
        super().__init__(hub, entry, device, "heat_energy")
        self._attr_native_value = 0.0
        self._last_power_w: float | None = None
        self._last_time: datetime | None = None

    async def async_added_to_hass(self) -> None:
        last = await self.async_get_last_sensor_data()
        if last is not None and isinstance(last.native_value, (int, float)):
            self._attr_native_value = float(last.native_value)
        await super().async_added_to_hass()

    @callback
    def _on_update(self) -> None:
        now = dt_util.utcnow()
        if self._last_power_w is not None and self._last_time is not None:
            seconds = (now - self._last_time).total_seconds()
            if 0 < seconds <= MAX_INTEGRATION_GAP_S:
                self._attr_native_value = float(self._attr_native_value or 0.0) + (
                    self._last_power_w * seconds / 3_600_000
                )
        self._last_power_w = self.hub.result.heat_output_w
        self._last_time = now
        self.async_write_ha_state()
