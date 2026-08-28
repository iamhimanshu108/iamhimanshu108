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

PALETTE = ("#00ff66", "#45ff8f", "#b6ff00", "#00d96f", "#7cffb2", "#c8ffd9")
SVG_MONO_FONT = "Fira Code, Menlo, Monaco, Consolas, Liberation Mono, monospace"


def get_json(url: str, payload: dict[str, Any] | None = None) -> Any:
    data = json.dumps(payload).encode("utf-8") if payload else None
    request = urllib.request.Request(url, data=data, headers=HEADERS, method="POST" if data else "GET")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def get_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
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
        batch = get_json(f"https://api.github.com/users/{USERNAME}/repos?type=owner&per_page=100&page={page}")
        repositories.extend(repo for repo in batch if not repo.get("fork"))
        if len(batch) < 100:
            return repositories
        page += 1


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
        raise RuntimeError("GITHUB_TOKEN is required to generate contribution statistics.")
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


def language_rows(languages: Counter[str]) -> list[tuple[str, int, float, str]]:
    total = sum(languages.values()) or 1
    return [(name, amount, amount / total * 100, PALETTE[index])
            for index, (name, amount) in enumerate(languages.most_common(6))]


def svg_document(width: int, height: int, body: str, title: str) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">{esc(title)}</title><desc id="desc">GitHub profile statistics for {esc(USERNAME)}.</desc>
  <rect width="{width}" height="{height}" rx="16" fill="#020804"/>
  <rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="15" fill="none" stroke="#00ff66" stroke-width="2"/>
  {body}
</svg>\n'''


def render_activity_svg(current: dict[str, Any], longest: dict[str, Any], contributions: int) -> str:
    values = [("CURRENT STREAK", f'{current["count"]} DAYS'),
              ("LONGEST STREAK", f'{longest["count"]} DAYS'),
              ("CONTRIBUTIONS / 1 YEAR", contributions)]
    blocks: list[str] = ['<text x="38" y="32" fill="#45ff8f" font-family="monospace" font-size="14" font-weight="bold">root@iamhimanshu:~$ github --activity</text>']
    for index, (label, value) in enumerate(values):
        x = 38 + index * 250
        if index:
            blocks.append(f'<path d="M{x - 30} 46v136" stroke="#176b38"/>')
        blocks.append(f'<text x="{x}" y="100" fill="#e5ffe9" font-family="{SVG_MONO_FONT}" font-size="46" font-weight="bold">{esc(value)}</text>')
        blocks.append(f'<text x="{x}" y="150" fill="#00ff66" font-family="{SVG_MONO_FONT}" font-size="15">&gt; {label}</text>')
    return svg_document(780, 180, ''.join(blocks), "Himanshu's GitHub activity")


def render_languages_svg(languages: Counter[str]) -> str:
    rows: list[str] = [
        '<defs>',
        '  <linearGradient id="langTrack" x1="0" y1="0" x2="1" y2="0">',
        '    <stop offset="0%" stop-color="#04180c"/>',
        '    <stop offset="100%" stop-color="#062211"/>',
        '  </linearGradient>',
        '</defs>',
        '<text x="38" y="32" fill="#45ff8f" font-family="monospace" font-size="14" font-weight="bold">root@iamhimanshu:~$ language --usage</text>',
        f'<text x="742" y="32" text-anchor="end" fill="#7cffb2" font-family="{SVG_MONO_FONT}" font-size="12">MOST USED</text>',
    ]

    for index, (name, _amount, percent, color) in enumerate(language_rows(languages)):
        y = 66 + index * 24
        bar_y = y - 11
        bar_width = max(450 * percent / 100, 3.0)

        # Bullet indicator
        rows.append(f'<circle cx="44" cy="{y - 4}" r="4.5" fill="{color}"/>')
        # Language name
        rows.append(f'<text x="60" y="{y}" fill="#c8ffd9" font-family="{SVG_MONO_FONT}" font-size="14">{esc(name)}</text>')
        # Track background
        rows.append(f'<rect x="200" y="{bar_y}" width="450" height="9" rx="4.5" fill="url(#langTrack)" stroke="#0d3d21" stroke-width="1"/>')
        # Filled bar
        rows.append(f'<rect x="200" y="{bar_y}" width="{bar_width:.1f}" height="9" rx="4.5" fill="{color}"/>')
        # Percentage
        rows.append(f'<text x="742" y="{y}" text-anchor="end" fill="#e5ffe9" font-family="{SVG_MONO_FONT}" font-size="13" font-weight="bold">{percent:.2f}%</text>')

    return svg_document(780, 215, ''.join(rows), "Himanshu's language contribution percentages")


def render_profile_gif(avatar: bytes, output: Path) -> None:
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
    body_font = load_mono_font(15)
    label_font = load_mono_font(14)
    code_lines = ("01001110 01000101 01010100 01010010 01010101 01001110", "sudo access --profile himanshu", "[OK] neural backend online", "encrypt://build.learn.repeat", "0x108 0xff 0x7a 0x01 0x00")
    for index, scan_y in enumerate((72, 108, 144, 180, 216, 252, 288, 324)):
        frame = Image.new("RGB", (1200, 420), "#020804")
        draw = ImageDraw.Draw(frame)
        draw.rounded_rectangle((8, 8, 1192, 412), radius=10, fill="#030d07", outline="#00ff66", width=2)
        draw.rectangle((10, 10, 1190, 58), fill="#06160b")
        draw.line((10, 59, 1190, 59), fill="#1e5e38", width=1)
        for x, color in ((32, "#ff5f56"), (54, "#ffbd2e"), (76, "#27c93f")):
            draw.ellipse((x - 6, 26 - 6, x + 6, 26 + 6), fill=color)
        draw.text((112, 17), "root@iamhimanshu:~$ ./identity --live", fill="#4dff91", font=header_font)

        # Low-contrast code stream gives the card a terminal/CRT feel without hiding the content.
        for row, text in enumerate(code_lines):
            draw.text((30, 76 + row * 25), text, fill="#062816", font=label_font)
            draw.text((900, 135 + row * 30), text[:25], fill="#041c0d", font=label_font)

        draw.rectangle((45, 88, 255, 302), outline="#26ff74", width=2)
        draw.line((45, 108, 65, 88), fill="#26ff74", width=3)
        draw.line((235, 88, 255, 108), fill="#26ff74", width=3)
        draw.line((45, 282, 65, 302), fill="#26ff74", width=3)
        draw.line((235, 302, 255, 282), fill="#26ff74", width=3)
        frame.paste(source, (60, 105), mask)
        # The animated matrix layer is deliberately clipped to the avatar, keeping the rest of the card still and readable.
        matrix = Image.new("RGBA", (180, 180), (0, 0, 0, 0))
        matrix_draw = ImageDraw.Draw(matrix)
        for y in range(14, 170, 26):
            for x in range(12, 170, 22):
                if (x - 90) ** 2 + (y - 90) ** 2 < 72 ** 2:
                    character = "01"[(x // 22 + y // 26 + index) % 2]
                    matrix_draw.text((x, y), character, fill=(0, 255, 102, 68), font=label_font)
        frame.paste(matrix, (60, 105), matrix)
        draw.ellipse((60, 105, 240, 285), outline="#00ff66", width=2)
        draw.line((70, 105 + ((index * 19) % 170), 230, 105 + ((index * 19) % 170)), fill="#77ffb0", width=2)
        draw.text((70, 315), "[ AVATAR VERIFIED ]", fill="#2cff78", font=label_font)

        terminal_lines = [("> WHOAMI: Himanshu Kumar Yadav", "#e5ffe9"),
                          ("> ROLE: MERN | Python | Gen AI | FastAPI", "#e5ffe9"),
                          ("> FOCUS: AI-powered backend development", "#e5ffe9"),
                          ("> STACK: MongoDB | Express | React | Node | FastAPI", "#e5ffe9")]
        for row, (text, color) in enumerate(terminal_lines):
            draw.text((290, 88 + row * 46), text, fill=color, font=body_font)
        cursor = "█" if index % 2 == 0 else " "
        draw.text((290, 300), f"root@iamhimanshu:~$ connect --now {cursor}", fill="#4dff91", font=label_font)
        draw.text((290, 332), "STATUS: ONLINE  |  LOCATION: INDIA  |  BUILDING IN PUBLIC", fill="#2b9e55", font=label_font)
        frames.append(frame)
    frames[0].save(output, save_all=True, append_images=frames[1:], duration=180, loop=0, optimize=True)


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    user = get_json(f"https://api.github.com/users/{USERNAME}")
    repositories = get_repositories()
    languages: Counter[str] = Counter()
    for repo in repositories:
        languages.update(get_json(repo["languages_url"]))
    created_at = datetime.fromisoformat(user["created_at"].replace("Z", "+00:00"))
    stats = get_contributions(created_at)
    render_profile_gif(fetch_avatar_bytes(user.get("avatar_url")), ASSETS / "profile-bio.gif")
    (ASSETS / "github-activity.svg").write_text(render_activity_svg(stats["current"], stats["longest"], stats["total"]), encoding="utf-8")
    (ASSETS / "language-contributions.svg").write_text(render_languages_svg(languages), encoding="utf-8")


if __name__ == "__main__":
    main()
