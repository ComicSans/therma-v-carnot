"""Integration tests in a real Home Assistant (pytest-homeassistant-custom-component).

The plugin brings its own ``custom_components`` package; this repo's folder is
appended to its path so Home Assistant finds the integration.
"""

from __future__ import annotations

import pathlib

import pytest

_OWN = str(pathlib.Path(__file__).resolve().parents[1] / "custom_components")

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    import custom_components  # the plugin's package, importable once it is loaded

    if _OWN not in custom_components.__path__:
        custom_components.__path__.append(_OWN)
    yield
