#!/usr/bin/env python3
"""Fetch public GitHub data and render local SVG cards for this profile README."""
from __future__ import annotations

import html
import json
import os
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
USERNAME = os.environ.get("GITHUB_USERNAME", "iamhimanshu108")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "profile-readme-updater"}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"


def get_json(url: str):
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def get_repositories():
    repositories, page = [], 1
    while True:
        batch = get_json(f"https://api.github.com/users/{USERNAME}/repos?type=owner&per_page=100&page={page}")
        repositories.extend(repo for repo in batch if not repo.get("fork"))
        if len(batch) < 100:
            return repositories
        page += 1


def svg_document(width: int, height: int, body: str) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">
  <rect width="{width}" height="{height}" rx="16" fill="#0d1117"/>
  <rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="15" fill="none" stroke="#263246" stroke-width="2"/>
  {body}
</svg>\n'''


def text(value: object) -> str:
    return html.escape(str(value))


def write_languages(languages: Counter[str]) -> None:
    total = sum(languages.values()) or 1
    colors = ["#00e5ff", "#a371f7", "#ff6b8a", "#f7c948", "#58a6ff", "#2ed573"]
    rows = []
    for index, (name, amount) in enumerate(languages.most_common(6)):
        percent = amount / total * 100
        y = 62 + index * 25
        width = round(430 * percent / 100, 1)
        color = colors[index]
        rows.append(f'<circle cx="42" cy="{y - 5}" r="5" fill="{color}"/>')
        rows.append(f'<text x="57" y="{y}" fill="#c9d1d9" font-family="monospace" font-size="13">{text(name)}</text>')
        rows.append(f'<rect x="215" y="{y - 12}" width="430" height="10" rx="5" fill="#263246"/>')
        rows.append(f'<rect x="215" y="{y - 12}" width="{width}" height="10" rx="5" fill="{color}"/>')
        rows.append(f'<text x="730" y="{y}" text-anchor="end" fill="#f0f6fc" font-family="monospace" font-size="13">{percent:.2f}%</text>')
    body = '<text x="38" y="32" fill="#00e5ff" font-family="monospace" font-size="14" font-weight="bold">LANGUAGE.CONTRIBUTIONS</text>' + ''.join(rows)
    (ASSETS / "language-contributions.svg").write_text(svg_document(780, 210, body), encoding="utf-8")


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    repos = get_repositories()
    languages: Counter[str] = Counter()
    for repo in repos:
        languages.update(get_json(repo["languages_url"]))
    write_languages(languages)


if __name__ == "__main__":
    main()
