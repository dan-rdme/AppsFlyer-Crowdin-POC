# Crowdin → ReadMe language sync

This repo connects a Crowdin GitHub integration to ReadMe's language branches.

## The problem

- Crowdin writes every language to **one branch**, under `translations/<lang>/docs/`, through a pull request.
- ReadMe reads each language from **its own branch**: `v1.0-<lang>`, with a translated category folder (for example `docs/マーケター/`).

## How it works

1. English changes land on `v1.0`.
2. Crowdin translates them and opens its PR into `v1.0` with `translations/<lang>/docs/...`.
3. Whenever `translations/**` or English `docs/**` changes on `v1.0`, the **Crowdin → ReadMe language branches** workflow runs. English on `v1.0` decides **which pages exist**. For each language in `enabled_languages`, it:
   - writes every translated page from `translations/<lang>/` into the translated category folder (`Marketers` → `マーケター`, ...)
   - **new pages:** a page that is new in English and not yet translated gets an English copy (fallback) until the translation arrives
   - **deleted or renamed pages:** a page that no longer exists in English is removed from the language branch. Leftover translation files for removed pages are ignored, so they are never recreated.
   - **menus:** every `_order.yaml` is copied from English, so new sections and pages appear in the language menus. The root `docs/_order.yaml`, which holds the translated category name, is left alone.
   - **links:** `/marketers/docs/x`, `/partners/docs/x`, `/…/reference/x` and `https://support.appsflyer.com/marketers/docs/x` become `/<project>/<lang>/…`, keeping anchors. Same-project (`/docs/x`) and external links are left alone.
   - opens a PR into `v1.0-<lang>`, or updates the open one, with a summary of what changed. With `auto_merge` set, it also merges the PR.
4. Someone merges the language PR, or it merges automatically. ReadMe syncs the branch and the language site updates.

If nothing changed for a language, it is skipped. The workflow can be run again safely: running it twice opens no duplicate PRs.

### Settings in `.github/crowdin-readme.json`

| Key | Default | What it does |
|---|---|---|
| `enabled_languages` | all mapped | Which language branches to manage |
| `english_fallback` | `true` | Add English copies of new, untranslated pages |
| `mirror_deletions` | `true` | Remove pages deleted or renamed in English |
| `sync_order_files` | `true` | Copy menus (`_order.yaml`) from English, except the root one |
| `link_sections` | `["docs"]` | Path sections to localize (`docs`, `reference`, ...) |
| `site_domains` | `[]` | Own domains whose absolute links should be localized |
| `auto_merge` | `false` | Merge language PRs automatically. Uses GitHub auto-merge when required checks exist. |

**Recommendation:** start with `auto_merge: false` and review the PRs for a few weeks, then switch it on. The Crowdin PR into `v1.0` is already the human review step.

**Renamed pages** get a new URL. Add a redirect from the old URL in ReadMe so existing links and bookmarks keep working.

## Files

| File | Purpose |
|---|---|
| `.github/workflows/crowdin-to-readme.yml` | The Action. Runs on push to `v1.0` that touches `translations/**` or `docs/**`, or manually. |
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
