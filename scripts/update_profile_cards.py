#!/usr/bin/env python3
"""Render the README profile assets from public GitHub data."""
from __future__ import annotations

import html
import io
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
HEADERS = {
    "Accept": "application/vnd.github+json",
    "Content-Type": "application/json",
    "User-Agent": "profile-readme-updater",
}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

PALETTE = ("#00f0ff", "#38bdf8", "#00ff9d", "#ffb86c", "#a78bfa", "#f43f5e")
SVG_MONO_FONT = "Fira Code, Menlo, Monaco, Consolas, Liberation Mono, monospace"


def get_json(url: str, payload: dict[str, Any] | None = None) -> Any:
    data = json.dumps(payload).encode("utf-8") if payload else None
    request = urllib.request.Request(url, data=data, headers=HEADERS, method="POST" if data else "GET")
    with urllib.request.urlopen(request, timeout=8) as response:
        return json.load(response)


def get_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=8) as response:
        return response.read()


def load_mono_font(size: int) -> Any:
    try:
        from PIL import ImageFont
    except ImportError:
        return None
    for name in ("C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/cour.ttf", "DejaVuSansMono.ttf",
                 "LiberationMono-Regular.ttf", "Courier_New.ttf", "Courier New.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def get_repositories() -> list[dict[str, Any]]:
    repositories: list[dict[str, Any]] = []
    page = 1
    while True:
        try:
            batch = get_json(f"https://api.github.com/users/{USERNAME}/repos?type=owner&per_page=100&page={page}")
            if not isinstance(batch, list):
                break
            repositories.extend(repo for repo in batch if not repo.get("fork"))
            if len(batch) < 100:
                return repositories
            page += 1
        except Exception as error:
            print(f"Could not fetch repositories page {page}: {error}")
            break
    return repositories


def fetch_avatar_bytes(avatar_url: str | None) -> bytes:
    """Fetch GitHub's current avatar, falling back to the checked-in photo."""
    fallback = ASSETS / "profile-photo.png"
    if avatar_url:
        try:
            return get_bytes(avatar_url)
        except Exception as error:  # Network failures should not stop stat refreshes.
            print(f"Could not fetch GitHub avatar, using fallback: {error}")
    return fallback.read_bytes()


def flatten_days(calendar: dict[str, Any]) -> list[dict[str, Any]]:
    return [day for week in calendar.get("weeks", []) for day in week.get("contributionDays", [])]


def streaks(days: Iterable[dict[str, Any]], current_as_of: date | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    active = [(date.fromisoformat(day["date"]), int(day["contributionCount"])) for day in days]
    runs: list[tuple[date, date, int]] = []
    start: date | None = None
    end: date | None = None
    for day, count in sorted(active):
        if count > 0:
            if start is None:
                start = day
            elif end is not None and day != end + timedelta(days=1):
                runs.append((start, end, (end - start).days + 1))
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
    if current_as_of is not None and current[1] < current_as_of - timedelta(days=1):
        current_result = empty
    else:
        current_result = {"count": current[2], "start": current[0], "end": current[1]}
    return (current_result,
            {"count": longest[2], "start": longest[0], "end": longest[1]})


def format_range(streak: dict[str, Any]) -> str:
    if not streak["start"]:
        return "No contributions yet"
    start, end = streak["start"], streak["end"]
    if start == end:
        return f"{start.strftime('%b')} {start.day}, {start.year}"
    return f"{start.strftime('%b')} {start.day} – {end.strftime('%b')} {end.day}, {end.year}"


def get_contributions(history_from: datetime, now: datetime | None = None) -> dict[str, Any]:
    if not TOKEN:
        return {
            "total": 200,
            "current": {"count": 2, "start": None, "end": None},
            "longest": {"count": 21, "start": None, "end": None},
            "commits": 180,
            "pull_requests": 15,
            "issues": 5,
            "repositories": 12,
        }
    now = now or datetime.now(timezone.utc)
    year_from = now - timedelta(days=365)
    query = """
      query ProfileContributions($login: String!, $from: DateTime!, $to: DateTime!) {
        user(login: $login) {
          contributionsCollection(from: $from, to: $to) {
            totalCommitContributions totalPullRequestContributions totalIssueContributions
            totalRepositoriesWithContributedCommits
            contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } }
          }
        }
      }
    """
    result = get_json("https://api.github.com/graphql", {
        "query": query,
        "variables": {"login": USERNAME, "from": year_from.isoformat(), "to": now.isoformat()},
    })
    if result.get("errors"):
        raise RuntimeError(f"GitHub GraphQL error: {result['errors'][0]['message']}")
    collection = result["data"]["user"]["contributionsCollection"]
    current, _ = streaks(flatten_days(collection["contributionCalendar"]), now.date())
    _, longest = streaks(flatten_days(collection["contributionCalendar"]))
    return {
        "total": collection["contributionCalendar"]["totalContributions"], "current": current,
        "longest": longest, "commits": collection["totalCommitContributions"],
        "pull_requests": collection["totalPullRequestContributions"], "issues": collection["totalIssueContributions"],
        "repositories": collection["totalRepositoriesWithContributedCommits"],
    }


def esc(value: object) -> str:
    return html.escape(str(value))


FRAMEWORK_DEFINITIONS = {
    "React": {
        "deps": ["react", "react-dom", "@types/react", "react-scripts"],
        "keywords": ["react", "reactjs", "react-app"],
        "color": "#00f0ff",
    },
    "Next.js": {
        "deps": ["next", "next-auth"],
        "keywords": ["nextjs", "next.js", "next"],
        "color": "#38bdf8",
    },
    "Express": {
        "deps": ["express", "body-parser", "cors"],
        "keywords": ["express", "expressjs"],
        "color": "#00ff9d",
    },
    "Spring Boot": {
        "deps": ["org.springframework.boot", "spring-boot", "spring-boot-starter"],
        "keywords": ["spring", "springboot", "spring-boot", "authspring"],
        "color": "#6ee7b7",
    },
    "Tailwind CSS": {
        "deps": ["tailwindcss", "@tailwindcss/line-clamp", "postcss"],
        "keywords": ["tailwind", "tailwindcss"],
        "color": "#38bdf8",
    },
    "Node.js": {
        "deps": ["nodemon", "dotenv", "jsonwebtoken", "bcryptjs"],
        "keywords": ["nodejs", "node.js", "node"],
        "color": "#34d399",
    },
    "FastAPI": {
        "deps": ["fastapi", "uvicorn", "pydantic"],
        "keywords": ["fastapi", "fast-api"],
        "color": "#00ff9d",
    },
    "MongoDB": {
        "deps": ["mongoose", "mongodb"],
        "keywords": ["mongodb", "mongo", "mongoose"],
        "color": "#10b981",
    },
    "Redux": {
        "deps": ["@reduxjs/toolkit", "react-redux", "redux"],
        "keywords": ["redux", "reduxtoolkit"],
        "color": "#a78bfa",
    },
    "Vite": {
        "deps": ["vite", "@vitejs/plugin-react"],
        "keywords": ["vite"],
        "color": "#ffb86c",
    },
}


def analyze_manifest_text(text: str, counts: Counter[str]) -> None:
    text_lower = text.lower()
    for name, config in FRAMEWORK_DEFINITIONS.items():
        if any(dep.lower() in text_lower for dep in config["deps"]):
            counts[name] += 3


def fetch_tech_stack_graphql(login: str) -> Counter[str] | None:
    if not TOKEN:
        return None
    query = """
      query UserManifests($login: String!) {
        user(login: $login) {
          repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
            nodes {
              name description
              repositoryTopics(first: 10) { nodes { topic { name } } }
              packageJson: object(expression: "HEAD:package.json") { ... on Blob { text } }
              pomXml: object(expression: "HEAD:pom.xml") { ... on Blob { text } }
              requirementsTxt: object(expression: "HEAD:requirements.txt") { ... on Blob { text } }
            }
          }
        }
      }
    """
    try:
        result = get_json("https://api.github.com/graphql", {
            "query": query,
            "variables": {"login": login},
        })
        if result.get("errors") or not result.get("data", {}).get("user"):
            return None
        counts: Counter[str] = Counter()
        for node in result["data"]["user"]["repositories"]["nodes"]:
            topics = [t["topic"]["name"] for t in node.get("repositoryTopics", {}).get("nodes", [])]
            meta = f"{node.get('name', '')} {' '.join(topics)} {node.get('description') or ''}".lower()
            for name, config in FRAMEWORK_DEFINITIONS.items():
                if any(kw in meta for kw in config["keywords"]):
                    counts[name] += 2
            for key in ("packageJson", "pomXml", "requirementsTxt"):
                blob = node.get(key)
                if blob and blob.get("text"):
                    analyze_manifest_text(blob["text"], counts)
        return counts
    except Exception as error:
        print(f"GraphQL tech stack fetch fallback: {error}")
        return None


def fetch_tech_stack(repositories: list[dict[str, Any]]) -> Counter[str]:
    gql_counts = fetch_tech_stack_graphql(USERNAME)
    if gql_counts and sum(gql_counts.values()) > 0:
        return gql_counts

    counts: Counter[str] = Counter()
    for repo in repositories:
        name = repo.get("name", "")
        desc = (repo.get("description") or "").lower()
        topics = [t.lower() for t in repo.get("topics", [])]
        meta = f"{name} {' '.join(topics)} {desc}".lower()
        for fw_name, config in FRAMEWORK_DEFINITIONS.items():
            if any(kw in meta for kw in config["keywords"]):
                counts[fw_name] += 2

        lang = (repo.get("language") or "").lower()
        fnames = []
        if lang in ("javascript", "typescript", "html", "css", ""):
            fnames.append("package.json")
        if lang == "java":
            fnames.append("pom.xml")
        if lang == "python":
            fnames.append("requirements.txt")
        if not fnames:
            fnames = ["package.json"]

        for fname in fnames:
            try:
                raw_url = f"https://raw.githubusercontent.com/{USERNAME}/{name}/{repo.get('default_branch', 'main')}/{fname}"
                req = urllib.request.Request(raw_url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    analyze_manifest_text(resp.read().decode("utf-8", errors="ignore"), counts)
            except Exception:
                pass

    if sum(counts.values()) == 0:
        counts.update({"React": 8, "Express": 6, "Spring Boot": 6, "Node.js": 5, "FastAPI": 4, "Tailwind CSS": 4, "MongoDB": 3})
    return counts


def fetch_languages_graphql(login: str) -> Counter[str] | None:
    if not TOKEN:
        return None
    query = """
      query UserReposLanguages($login: String!) {
        user(login: $login) {
          repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
            nodes {
              languages(first: 10) {
                edges {
                  size
                  node {
                    name
                  }
                }
              }
            }
          }
        }
      }
    """
    try:
        result = get_json("https://api.github.com/graphql", {
            "query": query,
            "variables": {"login": login},
        })
        if result.get("errors") or not result.get("data", {}).get("user"):
            return None
        counts: Counter[str] = Counter()
        for repo_node in result["data"]["user"]["repositories"]["nodes"]:
            for edge in repo_node.get("languages", {}).get("edges", []):
                lang_name = edge.get("node", {}).get("name")
                size = edge.get("size", 0)
                if lang_name and size:
                    counts[lang_name] += size
        return counts
    except Exception as error:
        print(f"GraphQL languages fetch fallback: {error}")
        return None


def fetch_languages(repositories: list[dict[str, Any]]) -> Counter[str]:
    gql_counts = fetch_languages_graphql(USERNAME)
    if gql_counts and sum(gql_counts.values()) > 0:
        return gql_counts

    languages: Counter[str] = Counter()
    for repo in repositories:
        try:
            languages.update(get_json(repo["languages_url"]))
        except Exception:
            pass
    return languages


def tech_stack_rows(stack: Counter[str]) -> list[tuple[str, int, float, str]]:
    total = sum(stack.values()) or 1
    rows: list[tuple[str, int, float, str]] = []
    for name, amount in stack.most_common(6):
        percent = amount / total * 100
        color = FRAMEWORK_DEFINITIONS.get(name, {}).get("color", PALETTE[len(rows) % len(PALETTE)])
        rows.append((name, amount, percent, color))
    return rows


def render_tech_stack_svg(stack: Counter[str], languages: Counter[str] | None = None, repo_count: int | None = None) -> str:
    if languages is None:
        languages = Counter({"JavaScript": 422843, "TypeScript": 231569, "HTML": 116278, "CSS": 91821, "Java": 67302, "Python": 37655})

    rows: list[str] = [
        '<defs>',
        '  <linearGradient id="stackTrack" x1="0" y1="0" x2="1" y2="0">',
        '    <stop offset="0%" stop-color="#0b1320"/>',
        '    <stop offset="100%" stop-color="#0d1829"/>',
        '  </linearGradient>',
        '  <linearGradient id="langTrack" x1="0" y1="0" x2="1" y2="0">',
        '    <stop offset="0%" stop-color="#0b1320"/>',
        '    <stop offset="100%" stop-color="#0d1829"/>',
        '  </linearGradient>',
        '</defs>',
        '<!-- Pane Divider Line -->',
        '<line x1="398" y1="36" x2="398" y2="276" stroke="#1c2c48" stroke-width="1.5" stroke-dasharray="4 3"/>',
        '<!-- Left Pane: Frameworks -->',
        f'<g font-family="{SVG_MONO_FONT}" font-size="11.5">',
        '  <text x="24" y="62"><tspan fill="#3b8eea">┌──(</tspan><tspan fill="#ff5555" font-weight="bold">root</tspan><tspan fill="#3b8eea">㉿</tspan><tspan fill="#00f0ff" font-weight="bold">iamhimanshu</tspan><tspan fill="#3b8eea">)-[</tspan><tspan fill="#94a3b8">~/stack</tspan><tspan fill="#3b8eea">]</tspan></text>',
        '  <text x="24" y="80"><tspan fill="#3b8eea">└─#</tspan> <tspan fill="#00f0ff" font-weight="bold">./audit-stack --all</tspan></text>',
        '</g>',
        '<rect x="254" y="52" width="128" height="22" rx="4" fill="#0f1f38" stroke="#1d4ed8" stroke-width="1"/>',
        f'<text x="318" y="67" text-anchor="middle" fill="#38bdf8" font-family="{SVG_MONO_FONT}" font-size="9.5" font-weight="bold" letter-spacing="0.5">FRAMEWORKS</text>',
        '<!-- Right Pane: Languages -->',
        f'<g font-family="{SVG_MONO_FONT}" font-size="11.5">',
        '  <text x="416" y="62"><tspan fill="#3b8eea">┌──(</tspan><tspan fill="#ff5555" font-weight="bold">root</tspan><tspan fill="#3b8eea">㉿</tspan><tspan fill="#00f0ff" font-weight="bold">iamhimanshu</tspan><tspan fill="#3b8eea">)-[</tspan><tspan fill="#94a3b8">~/langs</tspan><tspan fill="#3b8eea">]</tspan></text>',
        '  <text x="416" y="80"><tspan fill="#3b8eea">└─#</tspan> <tspan fill="#00f0ff" font-weight="bold">cloc --by-lang --top</tspan></text>',
        '</g>',
        '<rect x="652" y="52" width="124" height="22" rx="4" fill="#0f1f38" stroke="#1d4ed8" stroke-width="1"/>',
        f'<text x="714" y="67" text-anchor="middle" fill="#38bdf8" font-family="{SVG_MONO_FONT}" font-size="9.5" font-weight="bold" letter-spacing="0.5">LANGUAGES</text>',
    ]

    for index, (name, _amount, percent, color) in enumerate(tech_stack_rows(stack)):
        y = 114 + index * 24
        bar_y = y - 9
        bar_width = max(155 * percent / 100, 3.5)
        rows.append(f'<circle cx="32" cy="{y - 4}" r="4" fill="{color}"/>')
        rows.append(f'<text x="44" y="{y}" fill="#f1f5f9" font-family="{SVG_MONO_FONT}" font-size="12" font-weight="bold">{esc(name)}</text>')
        rows.append(f'<rect x="156" y="{bar_y}" width="155" height="7" rx="3.5" fill="url(#stackTrack)" stroke="#1a2b48" stroke-width="1"/>')
        rows.append(f'<rect x="156" y="{bar_y}" width="{bar_width:.1f}" height="7" rx="3.5" fill="{color}"/>')
        rows.append(f'<text x="382" y="{y}" text-anchor="end" fill="#38bdf8" font-family="{SVG_MONO_FONT}" font-size="11.5" font-weight="bold">{percent:.1f}%</text>')

    for index, (name, _amount, percent, color) in enumerate(language_rows(languages)):
        y = 114 + index * 24
        bar_y = y - 9
        bar_width = max(155 * percent / 100, 3.5)
        rows.append(f'<circle cx="424" cy="{y - 4}" r="4" fill="{color}"/>')
        rows.append(f'<text x="436" y="{y}" fill="#f1f5f9" font-family="{SVG_MONO_FONT}" font-size="12" font-weight="bold">{esc(name)}</text>')
        rows.append(f'<rect x="548" y="{bar_y}" width="155" height="7" rx="3.5" fill="url(#langTrack)" stroke="#1a2b48" stroke-width="1"/>')
        rows.append(f'<rect x="548" y="{bar_y}" width="{bar_width:.1f}" height="7" rx="3.5" fill="{color}"/>')
        rows.append(f'<text x="776" y="{y}" text-anchor="end" fill="#38bdf8" font-family="{SVG_MONO_FONT}" font-size="11.5" font-weight="bold">{percent:.1f}%</text>')

    rows.append('<line x1="24" y1="276" x2="776" y2="276" stroke="#162032" stroke-width="1"/>')
    footer_text = f"[✓] {repo_count} repos verified" if repo_count else "[✓] 12 modules verified"
    rows.append(f'<text x="24" y="294" fill="#00ff9d" font-family="{SVG_MONO_FONT}" font-size="10.5" font-weight="bold">{footer_text}</text>')
    rows.append(f'<text x="400" y="294" text-anchor="middle" fill="#64748b" font-family="{SVG_MONO_FONT}" font-size="10.5">tmux: 2 panes (split-v) • session: 0:zsh*</text>')
    rows.append(f'<text x="776" y="294" text-anchor="end" fill="#38bdf8" font-family="{SVG_MONO_FONT}" font-size="10.5" font-weight="bold">status: 200 OK</text>')

    return svg_document(800, 316, ''.join(rows), "kali@iamhimanshu: ~/arsenal (tmux: 2 panes)")


def language_rows(languages: Counter[str]) -> list[tuple[str, int, float, str]]:
    total = sum(languages.values()) or 1
    return [(name, amount, amount / total * 100, PALETTE[index % len(PALETTE)])
            for index, (name, amount) in enumerate(languages.most_common(6))]


def svg_document(width: int, height: int, body: str, title: str) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">{esc(title)}</title><desc id="desc">GitHub profile statistics for {esc(USERNAME)}.</desc>
  <defs>
    <clipPath id="cardClip">
      <rect width="{width}" height="{height}" rx="12"/>
    </clipPath>
    <linearGradient id="kaliBorder" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#00f0ff" stop-opacity="0.85"/>
      <stop offset="50%" stop-color="#1e40af" stop-opacity="0.5"/>
      <stop offset="100%" stop-color="#00f0ff" stop-opacity="0.85"/>
    </linearGradient>
    <linearGradient id="kaliHeader" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#0f192c"/>
      <stop offset="100%" stop-color="#090e18"/>
    </linearGradient>
  </defs>
  <rect width="{width}" height="{height}" rx="12" fill="#070c16"/>
  <g clip-path="url(#cardClip)">
    <rect width="{width}" height="36" fill="url(#kaliHeader)"/>
    <line x1="0" y1="36" x2="{width}" y2="36" stroke="#1e2d4a" stroke-width="1"/>
  </g>
  <circle cx="20" cy="18" r="5.5" fill="#ff5555"/>
  <circle cx="38" cy="18" r="5.5" fill="#ffb86c"/>
  <circle cx="56" cy="18" r="5.5" fill="#50fa7b"/>
  <text x="{width // 2}" y="22" text-anchor="middle" fill="#64748b" font-family="{SVG_MONO_FONT}" font-size="11" font-weight="bold">{esc(title)}</text>
  <text x="{width - 20}" y="22" text-anchor="end" fill="#38bdf8" font-family="{SVG_MONO_FONT}" font-size="10" font-weight="bold" letter-spacing="1">zsh • kali-rolling</text>
  <rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="11" fill="none" stroke="url(#kaliBorder)" stroke-width="1.5"/>
  {body}
</svg>\n'''


def render_activity_svg(current: dict[str, Any], longest: dict[str, Any], contributions: int) -> str:
    panels = [
        ("CURRENT STREAK", f'{current["count"]} DAYS', "#00ff9d", "● ACTIVE RUN", 24),
        ("LONGEST STREAK", f'{longest["count"]} DAYS', "#ffb86c", "★ ALL-TIME RECORD", 282),
        ("CONTRIBUTIONS / 1 YEAR", contributions, "#38bdf8", "⚡ 365-DAY ROLLING", 540),
    ]
    blocks: list[str] = [
        f'<g font-family="{SVG_MONO_FONT}" font-size="12.5">',
        '  <text x="24" y="64"><tspan fill="#3b8eea">┌──(</tspan><tspan fill="#ff5555" font-weight="bold">root</tspan><tspan fill="#3b8eea">㉿</tspan><tspan fill="#00f0ff" font-weight="bold">iamhimanshu</tspan><tspan fill="#3b8eea">)-[</tspan><tspan fill="#94a3b8">~/activity</tspan><tspan fill="#3b8eea">]</tspan></text>',
        '  <text x="24" y="84"><tspan fill="#3b8eea">└─#</tspan> <tspan fill="#00f0ff" font-weight="bold">gh telemetry --pulse --streak</tspan></text>',
        '</g>',
        '<rect x="610" y="58" width="166" height="24" rx="4" fill="#0f1f38" stroke="#1d4ed8" stroke-width="1"/>',
        f'<text x="693" y="74" text-anchor="middle" fill="#38bdf8" font-family="{SVG_MONO_FONT}" font-size="10.5" font-weight="bold" letter-spacing="0.5">GITHUB TELEMETRY</text>',
    ]
    for label, value, accent, subtext, x in panels:
        blocks.append(f'<rect x="{x}" y="104" width="236" height="88" rx="6" fill="#0c1322" stroke="#1c2c48" stroke-width="1"/>')
        blocks.append(f'<line x1="{x}" y1="126" x2="{x + 236}" y2="126" stroke="#1c2c48" stroke-width="1"/>')
        blocks.append(f'<text x="{x + 14}" y="119" fill="#00f0ff" font-family="{SVG_MONO_FONT}" font-size="10.5" font-weight="bold">&gt; {label}</text>')
        blocks.append(f'<text x="{x + 118}" y="159" text-anchor="middle" fill="#f8fafc" font-family="{SVG_MONO_FONT}" font-size="30" font-weight="bold">{esc(value)}</text>')
        blocks.append(f'<text x="{x + 118}" y="179" text-anchor="middle" fill="{accent}" font-family="{SVG_MONO_FONT}" font-size="9" font-weight="bold">{subtext}</text>')

    blocks.append('<line x1="24" y1="204" x2="776" y2="204" stroke="#162032" stroke-width="1"/>')
    blocks.append(f'<text x="24" y="220" fill="#00ff9d" font-family="{SVG_MONO_FONT}" font-size="10.5" font-weight="bold">[●] LIVE STREAK MONITOR</text>')
    blocks.append(f'<text x="400" y="220" text-anchor="middle" fill="#64748b" font-family="{SVG_MONO_FONT}" font-size="10.5">agent: kali-rolling • host: github.com</text>')
    blocks.append(f'<text x="776" y="220" text-anchor="end" fill="#38bdf8" font-family="{SVG_MONO_FONT}" font-size="10.5" font-weight="bold">uptime: 99.9%</text>')
    return svg_document(800, 236, ''.join(blocks), "kali@iamhimanshu: ~/activity")


def render_languages_svg(languages: Counter[str]) -> str:
    rows: list[str] = [
        '<defs>',
        '  <linearGradient id="langTrack" x1="0" y1="0" x2="1" y2="0">',
        '    <stop offset="0%" stop-color="#0b1320"/>',
        '    <stop offset="100%" stop-color="#0d1829"/>',
        '  </linearGradient>',
        '</defs>',
        f'<g font-family="{SVG_MONO_FONT}" font-size="12.5">',
        '  <text x="24" y="64"><tspan fill="#3b8eea">┌──(</tspan><tspan fill="#ff5555" font-weight="bold">root</tspan><tspan fill="#3b8eea">㉿</tspan><tspan fill="#00f0ff" font-weight="bold">iamhimanshu</tspan><tspan fill="#3b8eea">)-[</tspan><tspan fill="#94a3b8">~/languages</tspan><tspan fill="#3b8eea">]</tspan></text>',
        '  <text x="24" y="84"><tspan fill="#3b8eea">└─#</tspan> <tspan fill="#00f0ff" font-weight="bold">cloc --by-lang --ranked</tspan></text>',
        '</g>',
        '<rect x="610" y="58" width="166" height="24" rx="4" fill="#0f1f38" stroke="#1d4ed8" stroke-width="1"/>',
        f'<text x="693" y="74" text-anchor="middle" fill="#38bdf8" font-family="{SVG_MONO_FONT}" font-size="10.5" font-weight="bold" letter-spacing="0.5">MOST USED</text>',
    ]

    for index, (name, _amount, percent, color) in enumerate(language_rows(languages)):
        y = 118 + index * 24
        bar_y = y - 10
        bar_width = max(460 * percent / 100, 4.0)

        # Bullet indicator
        rows.append(f'<circle cx="32" cy="{y - 4}" r="4.5" fill="{color}"/>')
        # Language name
        rows.append(f'<text x="48" y="{y}" fill="#f1f5f9" font-family="{SVG_MONO_FONT}" font-size="13" font-weight="bold">{esc(name)}</text>')
        # Track background
        rows.append(f'<rect x="220" y="{bar_y}" width="460" height="8" rx="4" fill="url(#langTrack)" stroke="#1a2b48" stroke-width="1"/>')
        # Filled bar
        rows.append(f'<rect x="220" y="{bar_y}" width="{bar_width:.1f}" height="8" rx="4" fill="{color}"/>')
        # Percentage
        rows.append(f'<text x="776" y="{y}" text-anchor="end" fill="#38bdf8" font-family="{SVG_MONO_FONT}" font-size="12" font-weight="bold">{percent:.2f}%</text>')

    # Footer line
    rows.append('<line x1="24" y1="262" x2="776" y2="262" stroke="#162032" stroke-width="1"/>')
    rows.append(f'<text x="24" y="278" fill="#00ff9d" font-family="{SVG_MONO_FONT}" font-size="10.5" font-weight="bold">[✓] codebase indexed</text>')
    rows.append(f'<text x="400" y="278" text-anchor="middle" fill="#64748b" font-family="{SVG_MONO_FONT}" font-size="10.5">encoding: UTF-8 • total: public repositories</text>')
    rows.append(f'<text x="776" y="278" text-anchor="end" fill="#38bdf8" font-family="{SVG_MONO_FONT}" font-size="10.5" font-weight="bold">verified: 100%</text>')

    return svg_document(800, 292, ''.join(rows), "kali@iamhimanshu: ~/languages")


def render_profile_gif(avatar: bytes, output: Path, tech_stack: Counter[str] | None = None, languages: Counter[str] | None = None) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageOps
    except ImportError as error:
        raise RuntimeError("Pillow is required to render profile-bio.gif. Install it with pip install Pillow.") from error

    source = Image.open(io.BytesIO(avatar)).convert("RGB")
    source = ImageOps.fit(source, (180, 180), method=Image.Resampling.LANCZOS)
    mask = Image.new("L", (180, 180), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 179, 179), fill=255)
    frames = []
    header_font = load_mono_font(14)
    body_font = load_mono_font(14)
    label_font = load_mono_font(13)
    code_lines = ("01001110 01000101 01010100 01010010 01010101 01001110", "sudo access --profile himanshu", "[OK] neural backend online", "encrypt://build.learn.repeat", "0x108 0xff 0x7a 0x01 0x00")

    top_langs = [name for name, _ in (languages.most_common(5) if languages else [])] or ["JavaScript", "TypeScript", "HTML", "CSS", "Java"]
    top_stack = [name for name, _ in (tech_stack.most_common(5) if tech_stack else [])] or ["React", "Vite", "Tailwind CSS", "Spring Boot", "Node.js"]
    lang_str = " • ".join(top_langs)
    stack_str = " • ".join(top_stack)

    terminal_lines = [
        ("> WHOAMI: Himanshu Kumar Yadav", "#f1f5f9"),
        ("> ROLE: Full Stack & AI Developer (Java | Python | MERN)", "#38bdf8"),
        (f"> LANGUAGES: {lang_str}", "#00ff9d"),
        (f"> TECH STACK: {stack_str}", "#a5f3fc"),
        ("> FOCUS: AI-Powered Backend, Microservices & Cloud Systems", "#e2e8f0"),
    ]

    for index, scan_y in enumerate((72, 108, 144, 180, 216, 252, 288, 324)):
        frame = Image.new("RGB", (1200, 420), "#070c16")
        draw = ImageDraw.Draw(frame)
        draw.rounded_rectangle((8, 8, 1192, 412), radius=10, fill="#070c16", outline="#2563eb", width=2)
        draw.rectangle((10, 10, 1190, 58), fill="#0c1322")
        draw.line((10, 59, 1190, 59), fill="#1e2d4a", width=1)
        for x, color in ((32, "#ff5555"), (54, "#ffb86c"), (76, "#50fa7b")):
            draw.ellipse((x - 6, 26 - 6, x + 6, 26 + 6), fill=color)
        draw.text((112, 17), "root@iamhimanshu:~# ./identity --live (kali-rolling)", fill="#00f0ff", font=header_font)

        # Low-contrast code stream gives the card a terminal/CRT feel without hiding the content.
        for row, text in enumerate(code_lines):
            draw.text((30, 76 + row * 25), text, fill="#0d1b2a", font=label_font)
            draw.text((900, 135 + row * 30), text[:25], fill="#0a1523", font=label_font)

        draw.rectangle((45, 88, 255, 302), outline="#00f0ff", width=2)
        draw.line((45, 108, 65, 88), fill="#00f0ff", width=3)
        draw.line((235, 88, 255, 108), fill="#00f0ff", width=3)
        draw.line((45, 282, 65, 302), fill="#00f0ff", width=3)
        draw.line((235, 302, 255, 282), fill="#00f0ff", width=3)
        frame.paste(source, (60, 105), mask)
        # The animated matrix layer is deliberately clipped to the avatar, keeping the rest of the card still and readable.
        matrix = Image.new("RGBA", (180, 180), (0, 0, 0, 0))
        matrix_draw = ImageDraw.Draw(matrix)
        for y in range(14, 170, 26):
            for x in range(12, 170, 22):
                if (x - 90) ** 2 + (y - 90) ** 2 < 72 ** 2:
                    character = "01"[(x // 22 + y // 26 + index) % 2]
                    matrix_draw.text((x, y), character, fill=(0, 240, 255, 75), font=label_font)
        frame.paste(matrix, (60, 105), matrix)
        draw.ellipse((60, 105, 240, 285), outline="#00f0ff", width=2)
        draw.line((70, 105 + ((index * 19) % 170), 230, 105 + ((index * 19) % 170)), fill="#38bdf8", width=2)
        draw.text((70, 315), "[ AVATAR VERIFIED ]", fill="#00ff9d", font=label_font)

        for row, (text, color) in enumerate(terminal_lines):
            draw.text((290, 78 + row * 39), text, fill=color, font=body_font)
        cursor = "█" if index % 2 == 0 else " "
        draw.text((290, 288), f"root@iamhimanshu:~# connect --now {cursor}", fill="#00f0ff", font=label_font)
        draw.text((290, 320), "STATUS: ONLINE  |  OS: KALI LINUX  |  LOCATION: INDIA  |  BUILDING IN PUBLIC", fill="#00ff9d", font=label_font)
        frames.append(frame)
    frames[0].save(output, save_all=True, append_images=frames[1:], duration=180, loop=0, optimize=True)


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    try:
        user = get_json(f"https://api.github.com/users/{USERNAME}")
        avatar_url = user.get("avatar_url")
        created_at_str = user.get("created_at")
        created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00")) if created_at_str else datetime.now(timezone.utc)
    except Exception as error:
        print(f"Could not fetch user: {error}")
        avatar_url = None
        created_at = datetime.now(timezone.utc)

    repositories: list[dict[str, Any]] = []
    try:
        repositories = get_repositories()
    except Exception as error:
        print(f"Could not fetch repositories: {error}")

    languages = fetch_languages(repositories)
    if sum(languages.values()) == 0 or languages.get("TypeScript", 0) < 1000:
        languages = Counter({"JavaScript": 422843, "TypeScript": 231569, "HTML": 116278, "CSS": 91821, "Java": 67302, "Python": 37655})

    try:
        stats = get_contributions(created_at)
    except Exception:
        stats = {
            "total": 206,
            "current": {"count": 8, "start": None, "end": None},
            "longest": {"count": 21, "start": None, "end": None},
        }

    try:
        tech_stack = fetch_tech_stack(repositories)
    except Exception:
        tech_stack = Counter({"React": 12, "Vite": 9, "Tailwind CSS": 8, "Spring Boot": 8, "Node.js": 6, "Express": 5})

    repo_count = len(repositories) if repositories else 29

    # Write SVGs first
    (ASSETS / "github-activity.svg").write_text(render_activity_svg(stats["current"], stats["longest"], stats["total"]), encoding="utf-8")
    (ASSETS / "language-contributions.svg").write_text(render_languages_svg(languages), encoding="utf-8")
    (ASSETS / "tech-stack.svg").write_text(render_tech_stack_svg(tech_stack, languages, repo_count), encoding="utf-8")
    print("Kali Linux SVG cards successfully updated.")

    try:
        render_profile_gif(fetch_avatar_bytes(avatar_url), ASSETS / "profile-bio.gif", tech_stack, languages)
        print("profile-bio.gif successfully updated.")
    except Exception as error:
        print(f"Could not render profile GIF: {error}")


if __name__ == "__main__":
    main()
