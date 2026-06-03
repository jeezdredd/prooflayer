#!/usr/bin/env python3
"""
Sync wiki/ directory to GitHub Wiki repo.

Usage:
    python scripts/sync_github_wiki.py

Requires the GitHub wiki to be initialized first:
  1. Go to https://github.com/jeezdredd/prooflayer/wiki
  2. Click "Create the first page", save anything
  3. Run this script

The script flattens the wiki directory structure:
  wiki/index.md              -> Home.md
  wiki/analyzers/_index.md   -> Analyzers.md
  wiki/analyzers/ela.md      -> Analyzers-ela.md
  wiki/concepts/aggregation.md -> Concepts-aggregation.md
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_URL = "https://github.com/jeezdredd/prooflayer.wiki.git"
WIKI_DIR = Path(__file__).resolve().parent.parent / "wiki"


def flatten_path(rel_path: Path) -> str:
    parts = list(rel_path.parts)
    if not parts:
        return "Home.md"

    if len(parts) == 1:
        name = parts[0]
        if name == "index.md":
            return "Home.md"
        return name.replace(" ", "-")

    dir_part = parts[0].capitalize()
    file_part = parts[-1]

    if file_part == "_index.md":
        return f"{dir_part}.md"

    stem = Path(file_part).stem
    return f"{dir_part}-{stem}.md"


def fix_internal_links(content: str) -> str:
    def replace_link(m):
        text = m.group(1)
        href = m.group(2)
        if href.startswith("http") or href.startswith("#"):
            return m.group(0)

        parts = href.split("/")
        if len(parts) == 1:
            stem = parts[0]
            new_href = stem
        elif len(parts) == 2:
            dir_part = parts[0].capitalize()
            stem = parts[1]
            if stem == "_index" or stem == "":
                new_href = dir_part
            else:
                new_href = f"{dir_part}-{stem}"
        else:
            new_href = href.replace("/", "-")

        return f"[{text}]({new_href})"

    content = re.sub(r'\[\[([^\]]+)\]\]', lambda m: f"[{m.group(1).replace('/', ' - ')}]({_wikilink_to_href(m.group(1))})", content)
    content = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', replace_link, content)
    return content


def _wikilink_to_href(link: str) -> str:
    parts = link.split("/")
    if len(parts) == 1:
        return parts[0]
    dir_part = parts[0].capitalize()
    stem = parts[1]
    return f"{dir_part}-{stem}"


def build_sidebar(file_map: dict) -> str:
    lines = ["## ProofLayer Wiki\n"]
    lines.append("**[Home](Home)**\n")

    sections: dict[str, list[tuple[str, str]]] = {}
    top_level = []

    for src_rel, dest_name in sorted(file_map.items()):
        parts = Path(src_rel).parts
        page_name = dest_name[:-3]
        if len(parts) == 1:
            if dest_name != "Home.md":
                top_level.append((page_name, dest_name[:-3]))
        else:
            section = parts[0].capitalize()
            sections.setdefault(section, []).append((page_name, page_name))

    for name, href in top_level:
        lines.append(f"- [{name}]({href})")

    for section, pages in sorted(sections.items()):
        lines.append(f"\n**{section}**")
        for display, href in pages:
            lines.append(f"- [{display}]({href})")

    return "\n".join(lines)


def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Cloning {REPO_URL}...")
        result = subprocess.run(
            ["git", "clone", REPO_URL, tmpdir],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"Clone failed: {result.stderr}")
            print("Make sure the GitHub wiki is initialized first:")
            print("  1. Go to https://github.com/jeezdredd/prooflayer/wiki")
            print("  2. Create the first page (any content)")
            print("  3. Re-run this script")
            sys.exit(1)

        existing = list(Path(tmpdir).glob("*.md"))
        for f in existing:
            if not f.name.startswith("_"):
                f.unlink()

        file_map = {}
        for src in sorted(WIKI_DIR.rglob("*.md")):
            rel = src.relative_to(WIKI_DIR)
            dest_name = flatten_path(rel)
            file_map[str(rel)] = dest_name

            content = src.read_text(encoding="utf-8")
            content = fix_internal_links(content)

            dest = Path(tmpdir) / dest_name
            dest.write_text(content, encoding="utf-8")
            print(f"  {rel} -> {dest_name}")

        sidebar = build_sidebar(file_map)
        (Path(tmpdir) / "_Sidebar.md").write_text(sidebar, encoding="utf-8")
        print("  _Sidebar.md generated")

        subprocess.run(["git", "config", "user.email", "chesebastian01@gmail.com"], cwd=tmpdir)
        subprocess.run(["git", "config", "user.name", "jeezdredd"], cwd=tmpdir)
        subprocess.run(["git", "add", "-A"], cwd=tmpdir)

        status = subprocess.run(["git", "status", "--short"], cwd=tmpdir, capture_output=True, text=True)
        if not status.stdout.strip():
            print("No changes to push.")
            return

        subprocess.run(
            ["git", "commit", "-m", "sync wiki from repo wiki/ directory"],
            cwd=tmpdir
        )
        result = subprocess.run(["git", "push"], cwd=tmpdir, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Push failed: {result.stderr}")
            sys.exit(1)

        print("\nWiki synced successfully.")
        print("View at: https://github.com/jeezdredd/prooflayer/wiki")


if __name__ == "__main__":
    main()
