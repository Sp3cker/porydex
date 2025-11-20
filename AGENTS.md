# Porydex :: Agents' Field Guide

A fast orientation for coding assistants who need to touch `porydex` without poring over the whole repo.

## TL;DR
- `porydex` exports structured data from the upstream `pokeemerald-expansion` project so the custom Pokédex web app (Showdown fork) stays in sync.
- Work happens inside the `porydex/` subdirectory; run commands from here with the virtualenv activated.
– activate virtualenv with `source .venv bin/activate` before running porydex.
- After any parser or data change, run `python porydex.py extract --reload` to refresh cached ASTs and regenerate JSON in `site/data/`.

## Key Directories & Files
| Path | Why it matters |
| --- | --- |
| `porydex.py` | Entry-point CLI. Supports `config` and `extract` commands. |
| `porydex.ini` | Persisted configuration (expansion path, compiler, output dir, filters). Keep under version control. |
| `parse/` | Individual parsers for items, moves, species, encounters, etc. Each module focuses on one dataset and generally exposes a `parse_*` function plus helpers. |
| `data_loader.py` | Orchestrates every parser, merging outputs into the structures the exporters expect. |
| `generate.py` | Handles writing JSON files (and the Showdown fork assets) into `site/data/`. |
| `site/data/` | Generated artifacts (`items.json`, `moves.json`, `teachables.json`, …). Never hand-edit; regenerate via the CLI. |
| `vanilla/` | Canonical Showdown data (abilities, moves, etc.) used as fallbacks or for diffing. |


   Useful flags:
   - `--format {json,showdown}`: choose export style.
   - `--included-species-file`: limit Pokédex species (one per line, Showdown naming).
   - `--custom-ability-defs`: supply custom ability descriptions JSON.

## Everyday Workflow
1. **Activate the venv**: `source .venv/bin/activate` (prompt shows `(.venv)` when active).
2. **Make your code changes** (e.g., edit `parse/items.py`). Prefer small, well-scoped helpers; reuse `constants/` mappings instead of re-deriving data.
3. **Regenerate exports**:
   ```bash
   python porydex.py extract --reload
   ```
   - `--reload` blows away cached preprocessed C so parser changes take effect.
   - Add `--no-species` or other selective flags (see `porydex.py`) if you only need some datasets, but remember full exports before commit.
4. **Verify outputs**: inspect relevant files under `site/data/` or diff against `git`. For example:
   ```bash
   jq '.[] | select(.constantName == "ITEM_TM_X_SCISSOR")' site/data/items.json
   ```
5. **Mind warnings**: the move exporter currently logs missing Showdown type mappings for moves whose `type` token is `none`. They are noisy but expected—only treat new warnings as regressions.

## Architecture Notes
- Parsers typically read Expansion headers from `../pokeemerald-expansion/include/…` using regex/AST helpers. When adding new data:
  - Update or add helper builders (e.g., `build_item_constant_lookup`) instead of sprinkling ad-hoc parsing inline.
  - Keep parsers deterministic—avoid filesystem writes there; let `generate.py` handle serialization.
- Caches live under `.cache/` (managed automatically). Delete or use `--reload` if results look stale.
- Export order:
  1. `data_loader` aggregates.
  2. `generate.py` writes JSON and Showdown assets.
  3. `site/` hosts the static Pokédex (mdBook not required unless editing docs).

## Common Tasks Cheat Sheet
- **Add new item attributes**: edit `parse/items.py`, ensure the dict returned includes the new fields, and update consumers in `generate.py` if needed.

- **Inspect outputs quickly**: `jq`, `ripgrep`, or `python -m json.tool` against `site/data/*.json`.

## Troubleshooting
| Symptom | Likely fix |
| --- | --- |
| Export shows stale data | Rerun with `--reload` to rebuild cached preprocess results. |
| `gcc`/`clang` errors about missing headers | Confirm `config show` points `--expansion` at the correct repo and that submodules are pulled. |
| CLI missing | Ensure venv is active (`python` should be the local one). Otherwise, run `source .venv/bin/activate`. |
| Parser warning: `Unknown constant ITEM_*` | Extend the relevant constant lookup (e.g., combine TM macros with header IDs). |
| Mountains of `No type mapping found for 'none'` | Known issue in move exporter; document in PR but no action required unless counts grow unexpectedly. |

## Style & Review Tips
– Prefer to fix existing code than writing new code. Less code is preffered.
- Flag data-only changes separately from parser logic to simplify review.

Keep this guide updated when tooling or workflows change so future agents can get productive in minutes instead of hours.
