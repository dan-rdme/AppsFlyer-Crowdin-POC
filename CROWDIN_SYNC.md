# Crowdin → ReadMe language sync

This repo connects a Crowdin GitHub integration to ReadMe's language branches.

## The problem

- Crowdin writes every language to **one branch**, under `translations/<lang>/docs/`, through a pull request.
- ReadMe reads each language from **its own branch**: `v1.0-<lang>`, with a translated category folder (for example `docs/マーケター/`).

## How it works

1. English changes land on `v1.0`.
2. Crowdin translates them and opens its PR into `v1.0` with `translations/<lang>/docs/...`.
3. When that PR is merged, the **Crowdin → ReadMe language branches** workflow runs. For each language that changed, it:
   - copies `translations/<lang>/docs/**` onto `v1.0-<lang>`
   - renames the English category folder (`Marketers`) to the translated one
   - rewrites cross-project links: `/marketers/docs/x` → `/marketers/<lang>/docs/x`, `/partners/docs/x` → `/partners/<lang>/docs/x`
   - leaves every `_order.yaml` (navigation) untouched
   - opens a PR into `v1.0-<lang>`, or updates the open one. It never pushes directly to a language branch.
4. A reviewer merges the language PR. ReadMe syncs the branch and the language site updates.

If nothing changed for a language, it is skipped. The workflow can be run again safely: running it twice opens no duplicate PRs.

## Files

| File | Purpose |
|---|---|
| `.github/workflows/crowdin-to-readme.yml` | The Action. Runs on push to `v1.0` that touches `translations/**`, or manually. |
| `scripts/distribute_translations.py` | The logic. Plain Python 3 with no dependencies; it can run locally with `--dry-run`. |
| `.github/crowdin-readme.json` | Configuration: language code mapping, category names, which project slugs count as cross-project links. |
| `.github/workflows/simulate-crowdin.yml`, `scripts/simulate_crowdin.py` | **POC only.** Stand-in for Crowdin. Do not copy these into production. |

## Setup in a production repo

1. Copy the workflow, the script and the configuration file into the repo.
2. In **Settings → Actions → General**, enable **Allow GitHub Actions to create and approve pull requests**.
3. Adjust `.github/crowdin-readme.json`:
   - `languages`: map Crowdin's locale codes (`zh-CN`, `pt-BR`, ...) to ReadMe's branch suffixes (`zh`, `pt`, ...).
   - `category_names`: optional. If a language is missing here, the name is read from the first line of `docs/_order.yaml` on that language's branch.
4. In Crowdin, set the export path to `translations/%two_letters_code%/docs/...` (or the locale form you mapped), and turn on **Skip untranslated files**.

## Running it by hand

```sh
python3 scripts/distribute_translations.py --dry-run            # all languages found under translations/
python3 scripts/distribute_translations.py --langs ja --dry-run # one language
```

Or open **Actions → Crowdin → ReadMe language branches → Run workflow**.

## Known limitation: heading anchors

ReadMe generates heading anchors from the heading text. Translated headings therefore get translated anchors, and links to English anchors (`#partner-id-pid-parameter`) break on the language sites. The fix belongs in the English source: give each linked heading a fixed ID before translation, so every language keeps the same anchor.
