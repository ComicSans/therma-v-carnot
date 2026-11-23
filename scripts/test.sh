#!/bin/bash
# Fast tests: pytest of the pure model and static checks. Runs through the
# local run queue (local-ci, no device); the pre-push hook calls it.
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 64
# Outside the maintainer's machine there is no run queue: run directly.
Q="$HOME/GitHub/local-ci/share/sim-lauf.sh"
[ -n "${SIM_LAUF_ID:-}" ] || [ ! -x "$Q" ] || exec "$Q" --projekt therma-v-carnot \
  --zweck "${SIM_LAUF_ZWECK:-test}" --geraet keins -- "$PWD/scripts/test.sh" "$@"
set -euo pipefail
# Create the venv if missing and sync the dependencies on every run.
[ -d .venv ] || uv venv -q
uv pip install -q --python .venv/bin/python -r requirements_test.txt
.venv/bin/pytest -q "$@"
