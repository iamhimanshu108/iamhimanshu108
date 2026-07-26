# Developer Weekly Streak & Language Contributions

A compact, easy-to-read README layout to showcase a developer's weekly coding streak and language contribution breakdown.

---

## Weekly Streak

A simple 7-day view — mark days you coded with ✅.

<!-- STREAK_START -->
| Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| ⬜ | ✅ | ✅ | ✅ | ✅ | ⬜ | ⬜ |
<!-- STREAK_END -->

Tip: Replace boxes with ✅ for completed days. Example: `✅ ✅ ✅ ⬜ ⬜ ⬜ ⬜`.

---

## Language Contributions

Text-based bars let readers quickly scan your language mix. Update these numbers from your stats script.

| Language | Contribution |
|---|---:|
| Python | ████████ 45% |
| JavaScript | ██████ 30% |
| HTML/CSS | ███ 15% |
| Other | █ 10% |

Replace bars and percentages with real data from `scripts/update_language_stats.py`.

<!-- LANGUAGE_STATS_START -->
```text
📊 Language Contribution
⚡ Auto-updated from public repos • excluding forks

🟨 JavaScript   ██████████░░░░░░░░░░   51.82%
📄 HTML         ████░░░░░░░░░░░░░░░░   19.55%
🎨 CSS          ██░░░░░░░░░░░░░░░░░░   11.23%
☕ Java         ██░░░░░░░░░░░░░░░░░░    9.98%
🔷 TypeScript   █░░░░░░░░░░░░░░░░░░░    4.71%
🐍 Python       █░░░░░░░░░░░░░░░░░░░    2.60%
🧩 Others        ░░░░░░░░░░░░░░░░░░░░    0.12%
────────────────────────────────────────────
Repos: 37 | Forks ignored: 4 | Size: 0.61 MB | Updated: 2026-07-26
```
<!-- LANGUAGE_STATS_END -->

---

## Update Instructions

- Manual: edit this file and change the streak boxes and language table.
- Automated: run the repo script to regenerate language stats:

```bash
python3 scripts/update_language_stats.py
```

Want me to:
- Hook `scripts/update_language_stats.py` to write the language table into this README automatically,
- or add a GitHub Action to refresh it weekly?

---

Made simple — clear, minimal, and easy to automate.
