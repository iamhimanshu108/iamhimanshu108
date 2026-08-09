#!/usr/bin/env python3
"""Fetch public GitHub data and render local SVG cards for this profile README."""
from __future__ import annotations

import html
import json
import os
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
USERNAME = os.environ.get("GITHUB_USERNAME", "iamhimanshu108")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {"Accept": "application/vnd.github+json", "Content-Type": "application/json", "User-Agent": "profile-readme-updater"}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

PALETTE = ("#00d9ff", "#9b7bff", "#ef5b8d", "#f05252", "#4688d7", "#f97316")


def get_json(url: str, payload: dict[str, Any] | None = None) -> Any:
    data = json.dumps(payload).encode("utf-8") if payload else None
    request = urllib.request.Request(url, data=data, headers=HEADERS, method="POST" if data else "GET")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def get_repositories() -> list[dict[str, Any]]:
    repositories: list[dict[str, Any]] = []
    page = 1
    while True:
        batch = get_json(f"https://api.github.com/users/{USERNAME}/repos?type=owner&per_page=100&page={page}")
        repositories.extend(repo for repo in batch if not repo.get("fork"))
        if len(batch) < 100:
            return repositories
        page += 1


def flatten_days(calendar: dict[str, Any]) -> list[dict[str, Any]]:
    return [day for week in calendar.get("weeks", []) for day in week.get("contributionDays", [])]


def streaks(days: Iterable[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the latest-ending streak and longest streak from contribution days."""
    active = [(date.fromisoformat(day["date"]), int(day["contributionCount"])) for day in days]
    runs: list[tuple[date, date, int]] = []
    start: date | None = None
    end: date | None = None
    for day, count in sorted(active):
        if count > 0:
            if start is None:
                start = day
            end = day
        elif start is not None and end is not None:
            runs.append((start, end, (end - start).days + 1))
            start = end = None
    if start is not None and end is not None:
        runs.append((start, end, (end - start).days + 1))

    empty = {"count": 0, "start": None, "end": None}
    if not runs:
        return empty, empty.copy()
    current = runs[-1]
    longest = max(runs, key=lambda run: run[2])
    return ({"count": current[2], "start": current[0], "end": current[1]},
            {"count": longest[2], "start": longest[0], "end": longest[1]})


def format_range(streak: dict[str, Any]) -> str:
    if not streak["start"]:
        return "No contributions yet"
    start, end = streak["start"], streak["end"]
    def friendly(value: date, include_year: bool = True) -> str:
        suffix = f", {value.year}" if include_year else ""
        return f"{value.strftime('%b')} {value.day}{suffix}"
    if start == end:
        return friendly(start)
    return f"{friendly(start, include_year=False)} - {friendly(end)}"


def get_contributions(now: datetime | None = None) -> dict[str, Any]:
    if not TOKEN:
        raise RuntimeError("GITHUB_TOKEN is required to generate contribution statistics.")
    now = now or datetime.now(timezone.utc)
    start = now - timedelta(days=365)
    query = """
      query ProfileContributions($login: String!, $from: DateTime!, $to: DateTime!) {
        user(login: $login) {
          contributionsCollection(from: $from, to: $to) {
            totalCommitContributions
            totalPullRequestContributions
            totalIssueContributions
            totalRepositoriesWithContributedCommits
            contributionCalendar {
              totalContributions
              weeks { contributionDays { date contributionCount } }
            }
          }
        }
      }
    """
    result = get_json("https://api.github.com/graphql", {
        "query": query,
        "variables": {"login": USERNAME, "from": start.isoformat(), "to": now.isoformat()},
    })
    if result.get("errors"):
        raise RuntimeError(f"GitHub GraphQL error: {result['errors'][0]['message']}")
    collection = result["data"]["user"]["contributionsCollection"]
    current, longest = streaks(flatten_days(collection["contributionCalendar"]))
    return {
        "total": collection["contributionCalendar"]["totalContributions"],
        "current": current,
        "longest": longest,
        "commits": collection["totalCommitContributions"],
        "pull_requests": collection["totalPullRequestContributions"],
        "issues": collection["totalIssueContributions"],
        "repositories": collection["totalRepositoriesWithContributedCommits"],
    }


def esc(value: object) -> str:
    return html.escape(str(value))


def language_rows(languages: Counter[str]) -> list[tuple[str, int, float, str]]:
    total = sum(languages.values()) or 1
    return [(name, amount, amount / total * 100, PALETTE[index % len(PALETTE)])
            for index, (name, amount) in enumerate(languages.most_common(6))]


def svg_document(width: int, height: int, body: str, title: str) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">{esc(title)}</title>
  <desc id="desc">GitHub profile statistics for {esc(USERNAME)}.</desc>
  <rect width="{width}" height="{height}" rx="14" fill="#080e1d"/>
  {body}
</svg>\n'''


def render_statistics_svg(stats: dict[str, Any], stars: int, languages: Counter[str]) -> str:
    rows = language_rows(languages)
    top = [("TOTAL CONTRIBUTIONS", stats["total"], "Trailing 365 days", "#f4f7ff"),
           ("CURRENT STREAK", stats["current"]["count"], format_range(stats["current"]), "#9b7bff"),
           ("LONGEST STREAK", stats["longest"]["count"], format_range(stats["longest"]), "#f4f7ff")]
    top_parts = []
    for index, (label, value, caption, color) in enumerate(top):
        x = index * 400
        divider = "" if index == 0 else f'<path d="M{x} 26v126" stroke="#00d9ff" stroke-width="2" opacity=".8"/>'
        top_parts.append(f'''{divider}<text x="{x + 200}" y="60" text-anchor="middle" fill="{color}" font-family="monospace" font-size="30" font-weight="bold">{esc(value)}</text>
  <text x="{x + 200}" y="88" text-anchor="middle" fill="#99a8bf" font-family="monospace" font-size="12">{esc(label)}</text>
  <text x="{x + 200}" y="120" text-anchor="middle" fill="#64748b" font-family="monospace" font-size="11">{esc(caption)}</text>''')

    stat_lines = [("Total Stars Earned", stars), ("Total Commits", stats["commits"]),
                  ("Total PRs", stats["pull_requests"]), ("Total Issues", stats["issues"]),
                  ("Contributed to (last year)", stats["repositories"])]
    details = ''.join(
        f'<text x="48" y="{215 + index * 30}" fill="#9b7bff" font-family="monospace" font-size="16">{("★", "◉", "⑂", "!", "▣")[index]}</text>'
        f'<text x="77" y="{215 + index * 30}" fill="#9aa9bf" font-family="monospace" font-size="13">{esc(label)}:</text>'
        f'<text x="570" y="{215 + index * 30}" text-anchor="end" fill="#f4f7ff" font-family="monospace" font-size="13" font-weight="bold">{esc(value)}</text>'
        for index, (label, value) in enumerate(stat_lines))
    segments, legend = [], []
    cursor = 645
    for index, (name, _amount, percentage, color) in enumerate(rows):
        width = 510 * percentage / 100
        segments.append(f'<rect x="{cursor:.1f}" y="205" width="{width:.1f}" height="10" fill="{color}"/>')
        column = 645 + (index % 2) * 255
        y = 245 + (index // 2) * 30
        legend.append(f'<circle cx="{column}" cy="{y - 4}" r="5" fill="{color}"/><text x="{column + 12}" y="{y}" fill="#9aa9bf" font-family="monospace" font-size="11">{esc(name)} {percentage:.2f}%</text>')
        cursor += width
    body = f'''<rect x="10" y="10" width="1180" height="470" rx="10" fill="#0b1222" stroke="#17243a" stroke-width="2"/>
  {''.join(top_parts)}
  <rect x="22" y="170" width="570" height="285" rx="7" fill="#0a1120"/>
  <rect x="608" y="170" width="570" height="285" rx="7" fill="#0a1120"/>
  <text x="48" y="195" fill="#00d9ff" font-family="Arial, sans-serif" font-size="18" font-weight="bold">Himanshu's GitHub Stats</text>
  {details}
  <text x="645" y="195" fill="#00d9ff" font-family="Arial, sans-serif" font-size="18" font-weight="bold">Most Used Languages</text>
  <rect x="645" y="205" width="510" height="10" rx="5" fill="#25324a"/>
  {''.join(segments)}
  {''.join(legend)}
  <text x="645" y="365" fill="#64748b" font-family="monospace" font-size="11">Based on bytes in owned, non-fork repositories</text>'''
    return svg_document(1200, 490, body, "Himanshu's GitHub statistics")


def write_statistics(stats: dict[str, Any], stars: int, languages: Counter[str]) -> None:
    (ASSETS / "github-statistics.svg").write_text(render_statistics_svg(stats, stars, languages), encoding="utf-8")


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    repositories = get_repositories()
    languages: Counter[str] = Counter()
    for repo in repositories:
        languages.update(get_json(repo["languages_url"]))
    write_statistics(get_contributions(), sum(repo.get("stargazers_count", 0) for repo in repositories), languages)


if __name__ == "__main__":
    main()
