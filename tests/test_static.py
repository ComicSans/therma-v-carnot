"""Static checks of the integration files (no Home Assistant needed)."""

from __future__ import annotations

import ast
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = ROOT / "custom_components" / "therma_v_carnot"


def test_python_files_parse():
    for path in PKG.glob("*.py"):
        ast.parse(path.read_text(), filename=str(path))


def test_translations_equal_strings():
    assert json.loads((PKG / "strings.json").read_text()) == json.loads(
        (PKG / "translations" / "en.json").read_text()
    )


def test_every_sensor_key_has_a_name():
    strings = json.loads((PKG / "strings.json").read_text())
    names = strings["entity"]["sensor"]
    source = (PKG / "sensor.py").read_text()
    for key in names:
        assert f'"{key}"' in source
    for key in ("carnot_cop", "carnot_efficiency", "cop", "heat_output", "flow_rate", "heat_energy"):
        assert key in names


def test_manifest_and_hacs():
    manifest = json.loads((PKG / "manifest.json").read_text())
    assert manifest["domain"] == "therma_v_carnot"
    assert manifest["config_flow"] is True
    hacs = json.loads((ROOT / "hacs.json").read_text())
    assert hacs["name"] == manifest["name"]
