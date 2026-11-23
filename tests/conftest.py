"""Make the pure model importable without Home Assistant.

``custom_components/therma_v_carnot/__init__.py`` imports Home Assistant. The
model is deliberately HA-free, so the directory is registered as a bare
package ``therma_v_carnot`` without running that ``__init__``. If the model
ever imports Home Assistant, the tests fail: a guard that it stays pure.
"""

from __future__ import annotations

import pathlib
import sys
import types

_DIR = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "therma_v_carnot"

if "therma_v_carnot" not in sys.modules:
    _pkg = types.ModuleType("therma_v_carnot")
    _pkg.__path__ = [str(_DIR)]
    sys.modules["therma_v_carnot"] = _pkg
