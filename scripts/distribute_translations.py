#!/usr/bin/env python3
"""
Distribute Crowdin output into ReadMe's per-language branches.

Crowdin writes every language to ONE branch:
    translations/<crowdin-lang>/docs/<EnglishCategory>/...

ReadMe expects each language on its OWN branch:
    v1.0-<lang>:  docs/<TranslatedCategory>/...

For each language this script:
  1. Copies translations/<lang>/docs/** onto a work branch cut from v1.0-<lang>
  2. Renames the English category folder to the translated one
  3. Rewrites cross-project links  /marketers/docs/x -> /marketers/<lang>/docs/x
  4. Leaves _order.yaml (navigation) alone
  5. Opens (or updates) a PR into v1.0-<lang>   -- never pushes directly

Usage (CI or local):
    python3 scripts/distribute_translations.py [--langs ja,fr] [--dry-run] [--no-pr]

Requires: git, and `gh` (authenticated via GH_TOKEN) unless --no-pr / --dry-run.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
CONFIG = json.loads((ROOT / ".github" / "crowdin-readme.json").read_text(encoding="utf-8"))
WORK_BRANCH = "crowdin-sync/{target}"


def sh(*args: str, cwd: Path | None = None, check: bool = True, capture: bool = False) -> str:
    res = subprocess.run(args, cwd=cwd, check=check, text=True,
                         stdout=subprocess.PIPE if capture else None)
    return (res.stdout or "").strip() if capture else ""


def log(msg: str) -> None:
    print(msg, flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(msg + "\n")


def category_name(lang: str, worktree: Path) -> str:
    override = CONFIG.get("category_names", {}).get(lang)
    if override:
        return override
    order = worktree / "docs" / "_order.yaml"
    if order.exists():
        for line in order.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\s*-\s*['\"]?(.+?)['\"]?\s*$", line)
            if m:
                return m.group(1)
    return CONFIG["english_category"]


def link_rewriter(lang: str):
    slugs = "|".join(map(re.escape, CONFIG["cross_project_slugs"]))
    # Matches /marketers/docs/... or /partners/docs/... inside href="..." or ](...)
    # but NOT ones that already carry a language (/marketers/ja/docs/...).
    pat = re.compile(rf'(?P<pre>href="|\]\()(?P<proj>/(?:{slugs}))/docs/')

    def rewrite(text: str) -> tuple[str, int]:
        return pat.subn(lambda m: f'{m["pre"]}{m["proj"]}/{lang}/docs/', text)
    return rewrite


def process_language(crowdin_lang: str, args) -> dict:
    lang = CONFIG["languages"].get(crowdin_lang)
    if not lang:
        log(f"- `{crowdin_lang}`: no mapping in config, skipped")
        return {"lang": crowdin_lang, "status": "unmapped"}

    target = CONFIG["target_branch_pattern"].format(lang=lang)
    src_root = ROOT / CONFIG["translations_dir"] / crowdin_lang / "docs"
    if not src_root.is_dir():
        return {"lang": lang, "status": "no-files"}

    if sh("git", "ls-remote", "--heads", "origin", target, capture=True) == "":
        log(f"- `{lang}`: target branch `{target}` does not exist, skipped")
        return {"lang": lang, "status": "no-target-branch"}

    work = WORK_BRANCH.format(target=target)
    tmp = Path(tempfile.mkdtemp(prefix=f"wt-{lang}-"))
    sh("git", "fetch", "-q", "origin", target)
    sh("git", "worktree", "add", "-q", "-B", work, str(tmp), f"origin/{target}")
    try:
        cat = category_name(lang, tmp)
        rewrite = link_rewriter(lang)
        copied = links = 0
        for src in sorted(src_root.rglob("*")):
            if not src.is_file() or src.name in CONFIG["skip_files"]:
                continue
            rel = src.relative_to(src_root)
            parts = list(rel.parts)
            if parts and parts[0] == CONFIG["english_category"]:
                parts[0] = cat
            dest = tmp / "docs" / Path(*parts)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if src.suffix in (".md", ".mdx"):
                text, n = rewrite(src.read_text(encoding="utf-8"))
                links += n
                dest.write_text(text, encoding="utf-8")
            else:
                shutil.copyfile(src, dest)
            copied += 1

        sh("git", "add", "-A", "docs", cwd=tmp)
        changed = sh("git", "diff", "--cached", "--name-only", cwd=tmp, capture=True).splitlines()
        if not changed:
            log(f"- `{lang}`: {copied} files checked, no changes vs `{target}`")
            return {"lang": lang, "status": "unchanged"}

        log(f"- `{lang}`: {len(changed)} changed file(s) -> `{target}` (folder `{cat}`, {links} links localized)")
        if args.dry_run:
            for c in changed[:20]:
                log(f"    - {c}")
            return {"lang": lang, "status": "dry-run", "changed": len(changed)}

        src_sha = sh("git", "rev-parse", "--short", "HEAD", capture=True)
        sh("git", "-c", "user.name=crowdin-readme-sync[bot]",
           "-c", "user.email=crowdin-readme-sync@users.noreply.github.com",
           "commit", "-q", "-m", f"Crowdin: sync {lang} translations from {CONFIG['source_branch']}@{src_sha}", cwd=tmp)
        sh("git", "push", "-q", "--force", "origin", f"{work}:{work}", cwd=tmp)

        if args.no_pr:
            return {"lang": lang, "status": "pushed", "changed": len(changed)}

        body = (f"Automated sync of **{lang}** translations from Crowdin.\n\n"
                f"- Source: `{CONFIG['translations_dir']}/{crowdin_lang}/docs/` on `{CONFIG['source_branch']}` @ `{src_sha}`\n"
                f"- Category folder: `{CONFIG['english_category']}` -> `{cat}`\n"
                f"- Cross-project links localized: {links}\n"
                f"- `_order.yaml` files untouched\n- Files changed: {len(changed)}\n\n"
                "Merging this PR lets ReadMe sync the language site.")
        existing = sh("gh", "pr", "list", "--head", work, "--base", target, "--state", "open",
                      "--json", "url", "-q", ".[0].url", capture=True)
        if existing:
            sh("gh", "pr", "edit", existing, "--body", body)
            log(f"    updated PR {existing}")
            url = existing
        else:
            url = sh("gh", "pr", "create", "--head", work, "--base", target,
                     "--title", f"Crowdin → ReadMe: {lang} translations", "--body", body, capture=True)
            log(f"    opened PR {url}")
        return {"lang": lang, "status": "pr", "url": url, "changed": len(changed)}
    finally:
        sh("git", "worktree", "remove", "--force", str(tmp), check=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--langs", help="comma-separated Crowdin language codes (default: all found)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-pr", action="store_true", help="push work branches but do not open PRs")
    args = ap.parse_args()

    tdir = ROOT / CONFIG["translations_dir"]
    found = sorted(p.name for p in tdir.iterdir() if p.is_dir()) if tdir.is_dir() else []
    langs = [l.strip() for l in args.langs.split(",")] if args.langs else found
    if not langs:
        log("No translations found; nothing to do.")
        return 0

    log(f"### Crowdin → ReadMe sync ({', '.join(langs)})")
    results = [process_language(l, args) for l in langs]
    print(json.dumps(results, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
