#!/usr/bin/env python3
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
USERNAME = os.environ.get("GITHUB_USERNAME", "iamhimanshu108")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

HEADERS = {"Accept": "application/vnd.github+json"}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"


def fetch_json(url: str):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def fetch_repos(username: str):
    repos = []
    page = 1
    while True:
        url = f"https://api.github.com/users/{username}/repos?per_page=100&page={page}&type=all"
        page_data = fetch_json(url)
        if not page_data:
            break
        repos.extend(page_data)
        if len(page_data) < 100:
            break
        page += 1
    return repos


def build_stats(username: str) -> str:
    repos = fetch_repos(username)
    total_repositories = 0
    forks_ignored = 0
    language_bytes = {}
    total_code_bytes = 0

    for repo in repos:
        if repo.get("fork"):
            forks_ignored += 1
            continue

        total_repositories += 1
        repo_languages = fetch_json(repo["languages_url"])
        for lang, size in repo_languages.items():
            language_bytes[lang] = language_bytes.get(lang, 0) + size
            total_code_bytes += size

    icon_map = {
        "Python": "🐍",
        "JavaScript": "🟨",
        "TypeScript": "🔷",
        "Java": "☕",
        "CSS": "🎨",
        "HTML": "📄",
    }

    sorted_languages = sorted(language_bytes.items(), key=lambda item: item[1], reverse=True)
    top_languages = []
    for name, size in sorted_languages:
        if len(top_languages) >= 6:
            break
        top_languages.append((name, size))

    selected_total = sum(size for _, size in top_languages)
    others_bytes = max(total_code_bytes - selected_total, 0)

    lines = ["📊 Language Contribution", "⚡ Auto-updated from public repos • excluding forks", ""]

    for name, size in top_languages:
        percentage = (size / total_code_bytes * 100) if total_code_bytes else 0.0
        bar_width = 20
        filled = int(round(percentage / 100 * bar_width)) if total_code_bytes else 0
        filled = max(0, min(bar_width, filled))
        icon = icon_map.get(name, "🧩")
        lines.append(f"{icon} {name:<12} {'█' * filled}{'░' * (bar_width - filled)}  {percentage:>6.2f}%")

    if others_bytes:
        percentage = (others_bytes / total_code_bytes * 100) if total_code_bytes else 0.0
        bar_width = 20
        filled = int(round(percentage / 100 * bar_width)) if total_code_bytes else 0
        filled = max(0, min(bar_width, filled))
        lines.append(f"🧩 Others        {'█' * filled}{'░' * (bar_width - filled)}  {percentage:>6.2f}%")
    else:
        lines.append("🧩 Others        ░░░░░░░░░░░░░░░░░  0.00%")

    total_code_mb = round(total_code_bytes / (1024 * 1024), 2)
    updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    block = f"""```text
{'\n'.join(lines)}
────────────────────────────────────────────
Repos: {total_repositories} | Forks ignored: {forks_ignored} | Size: {total_code_mb:.2f} MB | Updated: {updated_at}
```"""
    return block


def replace_readme_block(content: str, new_block: str) -> str:
    pattern = re.compile(r"<!-- LANGUAGE_STATS_START -->.*?<!-- LANGUAGE_STATS_END -->", re.S)
    if not pattern.search(content):
        raise RuntimeError("README markers were not found")
    return pattern.sub(f"<!-- LANGUAGE_STATS_START -->\n{new_block}\n<!-- LANGUAGE_STATS_END -->", content)


def main():
    try:
        new_block = build_stats(USERNAME)
    except Exception as exc:
        print(f"Failed to fetch language stats: {exc}", file=sys.stderr)
        raise

    readme_content = README_PATH.read_text(encoding="utf-8")
    updated = replace_readme_block(readme_content, new_block)
    README_PATH.write_text(updated, encoding="utf-8")
    print(f"Updated README language stats for {USERNAME}")


if __name__ == "__main__":
    main()
