#!/usr/bin/env python3
"""
Simulate Crowdin's GitHub integration (POC only — not shipped to AppsFlyer).

Crowdin's real behaviour (per Oleh, Nov 4):
  * all languages land on ONE branch under translations/<lang>/docs/
  * English folder names and English (non-localized) links, mirroring the source
  * delivered through a PR into the source branch

This script builds that output from the current v1.0-<lang> branches (so the
"translations" are real AppsFlyer content), optionally stamps a visible test
change, and writes it to translations/<lang>/docs/ in the working tree.

    python3 scripts/simulate_crowdin.py --langs ja,fr,es --stamp "Crowdin test 1"
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
CONFIG = json.loads((ROOT / ".github" / "crowdin-readme.json").read_text(encoding="utf-8"))
# Crowdin locale codes we pretend to emit, keyed by ReadMe lang
CROWDIN_CODE = {"zh": "zh-CN", "pt": "pt-BR"}


def sh(*a, cwd=None, capture=False):
    r = subprocess.run(a, cwd=cwd, check=True, text=True, stdout=subprocess.PIPE if capture else None)
    return (r.stdout or "").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--langs", default="ja,fr,es")
    ap.add_argument("--stamp", help="text appended to the first page's excerpt to make a visible change")
    ap.add_argument("--page", default="get-started/manage-your-account/account-security/audit-log.md",
                    help="page (relative to the category folder) to stamp")
    args = ap.parse_args()

    slugs = "|".join(CONFIG["cross_project_slugs"])
    for lang in [l.strip() for l in args.langs.split(",")]:
        target = CONFIG["target_branch_pattern"].format(lang=lang)
        code = CROWDIN_CODE.get(lang, lang)
        out = ROOT / CONFIG["translations_dir"] / code / "docs" / CONFIG["english_category"]
        sh("git", "fetch", "-q", "origin", target)
        with tempfile.TemporaryDirectory() as tmp:
            sh("git", "worktree", "add", "-q", "--detach", tmp, f"origin/{target}")
            try:
                docs = Path(tmp) / "docs"
                cat_dir = next(p for p in docs.iterdir() if p.is_dir())
                n = 0
                for f in cat_dir.rglob("*.md"):
                    rel = f.relative_to(cat_dir)
                    text = f.read_text(encoding="utf-8")
                    # Crowdin keeps the English link targets from the source file
                    text = re.sub(rf'(href="|\]\()/({slugs})/{re.escape(lang)}/docs/', r'\1/\2/docs/', text)
                    if args.stamp and rel.as_posix() == args.page:
                        text = re.sub(r"^(title: .*)$", rf"\1 [{args.stamp}]", text, count=1, flags=re.M)
                    dest = out / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_text(text, encoding="utf-8")
                    n += 1
                print(f"{lang}: wrote {n} files to {out.relative_to(ROOT)}")
            finally:
                sh("git", "worktree", "remove", "--force", tmp)


if __name__ == "__main__":
    main()
