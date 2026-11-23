# CLAUDE.md

Rules for Claude Code in this repo. What the integration does and how to set it
up is in `README.md`.

## What this is

Home Assistant custom integration (`custom_components/therma_v_carnot`),
distributed through HACS: estimated heat output, COP and flow rate from the
Carnot limit, as an add-on to `~/GitHub/lg-therma-v-esphome-modbus`. The repo
is public (exception REMOTE in `~/GitHub/local-ci/ausnahmen.tsv`): nothing
internal, no credentials, no real house data in tests or docs.

## Rules

- Everything in English: code, comments, UI strings, docs.
- `model.py` stays free of Home Assistant imports; its tests run without HA.
- `strings.json` and `translations/en.json` stay identical.
- Tests: `scripts/test.sh` (pytest in `.venv`, through the run queue); the
  pre-push hook of local-ci calls it.
- Release: tag and `manifest.json` version match; publish only after Tobias'
  yes.
- `~/.claude/CLAUDE.md` applies globally.
