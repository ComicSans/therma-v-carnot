# Therma V Carnot

Home Assistant integration that estimates heat output, COP and water flow rate
of an LG Therma V heat pump without a flow meter. It is an add-on to the
[lg-therma-v-esphome-modbus](https://github.com/ComicSans/lg-therma-v-esphome-modbus)
firmware. That firmware only reports measured values, and Modbus has no flow
rate, so it cannot report heat output or COP. This integration fills the gap
with a model. Its results are **estimates**.

The model was proposed in
[lg-therma-v-esphome-modbus#17](https://github.com/ComicSans/lg-therma-v-esphome-modbus/issues/17).

## Related projects

- [lg-therma-v-esphome-modbus](https://github.com/ComicSans/lg-therma-v-esphome-modbus):
  the ESPHome firmware that reads the heat pump over Modbus and provides the
  source entities.
- [hahems](https://github.com/ComicSans/hahems): home energy management for Home
  Assistant, also installed through HACS. It plans battery, hot water and other
  loads and can switch them; this integration only estimates.

## The model

1. **Carnot COP**, the theoretical limit between a warm and a cold temperature
   (in kelvin): `COP_carnot = T_warm / (T_warm − T_cold)`.
2. **Carnot efficiency**, the share of that limit the unit actually reaches. It
   depends on the water delta T (flow minus return). Default calibration: 40 % at
   2 K and below, 55 % at 5 K and above, linear in between.
3. **Estimated COP** = Carnot efficiency × Carnot COP.
4. **Estimated heat output** = COP × (electric power − auxiliary power). The
   auxiliary power (default 100 W) covers the controller, inverter losses, pump
   and fan, which do not drive the compressor. Without it, the heat output reads
   far too high at low load.
5. **Estimated flow rate** = heat output / (69.34 W per L/min and K × delta T).

The flow rate is derived from the heat output, so it can be checked against the
flow rate on the control panel. On the unit where the model was calibrated, the
reporter found it within 0.2 L/min in steady operation.

While the compressor is off or the unit defrosts, heat output is 0 and COP and
flow rate are unknown. If the compressor signal is unavailable, heat output is
unknown too and the heat energy skips that time. A defrost takes heat from the water. The model does not
count that, so the heat energy reads slightly high.

## Temperature basis

You choose the Carnot temperatures when adding the integration:

| Basis | Warm side | Cold side | Notes |
|---|---|---|---|
| Water | water flow temperature | outdoor temperature | Carnot efficiency also contains the heat exchanger losses on both sides, so it depends strongly on the installation. |
| Refrigerant | condensing temperature | evaporating temperature | Closer to the compressor's own efficiency and less dependent on the installation. Needs the condensing and evaporating temperatures from the firmware. |

The refrigerant basis has the larger temperature lift, so its Carnot COP is
lower and the unit reaches a larger share of it. The default calibration was
not made for it. **With the refrigerant basis, calibrate the efficiency for your
unit** (see below).

## Limits

- The default constants come from one unit (model, refrigerant and outdoor unit
  firmware of the reporter). Other units differ.
- Carnot efficiency depends only on delta T here. Compressor speed, pressure
  ratio, vapor injection and the refrigerant charge also affect it and are not
  modelled.
- Electric power must cover the whole unit and come from a meter. The quality of
  the result depends on it.
- Flow rate is not reported below 0.5 K delta T.

## Installation

1. HACS → Integrations → ⋮ → Custom repositories → add
   `https://github.com/ComicSans/therma-v-carnot` as type *Integration*.
2. Install **Therma V Carnot** and restart Home Assistant.
3. Settings → Devices & services → Add integration → **Therma V Carnot**.
4. Choose the temperature basis, then the source entities. Entities of the
   lg-therma-v-esphome-modbus firmware are suggested:

   | Source | Firmware entity (suffix) |
   |---|---|
   | Water flow temperature | `sensor…_water_flow_temperature` |
   | Water return temperature | `sensor…_water_return_temperature` |
   | Outdoor temperature (water basis) | `sensor…_outdoor_temperature_unit_sensor` |
   | Condensing temperature (refrigerant basis) | `sensor…_condensing_temperature` |
   | Evaporating temperature (refrigerant basis) | `sensor…_evaporating_temperature` |
   | Electric power | `sensor…_active_power_measured` |
   | Compressor running | `binary_sensor…_compressor_running` |
   | Defrost active (optional) | `binary_sensor…_defrost_active` |

   Other heat pumps work too if they provide these values. Temperatures in °C,
   °F or K, power in W or kW.

To change the source entities, remove the integration and add it again. The
calibration is in the integration's options.

## Sensors

| Sensor | Unit | Meaning |
|---|---|---|
| Carnot COP | — | theoretical limit |
| Carnot efficiency | % | share of the limit (from delta T) |
| Estimated COP | — | efficiency × Carnot COP |
| Estimated heat output | W | COP × (electric power − auxiliary power) |
| Estimated flow rate | L/min | heat output / (69.34 × delta T) |
| Estimated heat energy | kWh | sum of the heat output over time, for the energy dashboard |

The values update with every change of a source entity and at least once a
minute.

## Calibration

The options hold five constants: efficiency at low and high delta T, the two
delta T points, and the auxiliary power.

To calibrate them, you need periods where the real heat output is known, for
example with a fixed pump speed and the flow rate read on the control panel:

1. Run the pump at a fixed speed and note the flow rate (L/min).
2. In steady operation (compressor running for at least 15 minutes, no defrost),
   compute the real heat output: `flow × 69.34 × delta T` (W).
3. Real COP = heat output / (electric power − auxiliary power).
4. Efficiency = real COP / Carnot COP (the sensor shows Carnot COP).
5. Repeat at several delta T values and enter the efficiency at the low and the
   high point.

If the estimated flow rate then matches the panel within a few tenths of a L/min,
the calibration fits.

## Development

`scripts/test.sh` runs the tests of the pure model (`model.py`, no Home Assistant
needed). `tests_ha/` tests the config flow and the sensors in a real Home
Assistant (`pip install -r requirements_ha.txt`, then
`pytest -c tests_ha/pytest.ini --rootdir . tests_ha`). GitHub Actions run both,
plus hassfest and the HACS validation.

## License

MIT, see [LICENSE](LICENSE).
