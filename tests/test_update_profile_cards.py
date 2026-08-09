from collections import Counter
from datetime import date
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import update_profile_cards as cards


class ProfileCardTests(unittest.TestCase):
    def test_streaks_allows_today_or_yesterday_for_current_streak(self):
        days = [
            {"date": "2026-01-01", "contributionCount": 1},
            {"date": "2026-01-02", "contributionCount": 1},
            {"date": "2026-01-03", "contributionCount": 0},
            {"date": "2026-01-04", "contributionCount": 1},
        ]
        current, longest = cards.streaks(days, date(2026, 1, 5))
        self.assertEqual(current["count"], 1)
        self.assertEqual(current["start"], date(2026, 1, 4))
        self.assertEqual(longest["count"], 2)

    def test_streaks_returns_zero_when_the_latest_run_is_broken(self):
        days = [
            {"date": "2026-01-01", "contributionCount": 1},
            {"date": "2026-01-02", "contributionCount": 1},
            {"date": "2026-01-03", "contributionCount": 0},
        ]
        current, _ = cards.streaks(days, date(2026, 1, 5))
        self.assertEqual(current["count"], 0)

    def test_streaks_finds_the_longest_run_in_all_history(self):
        days = [
            {"date": "2022-01-01", "contributionCount": 1},
            {"date": "2022-01-02", "contributionCount": 1},
            {"date": "2022-01-03", "contributionCount": 1},
            {"date": "2026-01-01", "contributionCount": 1},
            {"date": "2026-01-02", "contributionCount": 0},
        ]
        _, longest = cards.streaks(days)
        self.assertEqual(longest["count"], 3)

    def test_language_rows_are_sorted_limited_and_weighted(self):
        rows = cards.language_rows(Counter({"Python": 70, "JavaScript": 20, "HTML": 10, "CSS": 1, "Go": 1, "Rust": 1, "Java": 1}))
        self.assertEqual([row[0] for row in rows], ["Python", "JavaScript", "HTML", "CSS", "Go", "Rust"])
        self.assertAlmostEqual(rows[0][2], 67.307, places=2)

    def test_avatar_fetch_uses_github_response_and_falls_back_on_error(self):
        with patch.object(cards, "get_bytes", return_value=b"github-avatar"):
            self.assertEqual(cards.fetch_avatar_bytes("https://avatars.example/avatar.png"), b"github-avatar")
        with patch.object(cards, "get_bytes", side_effect=OSError("offline")):
            self.assertEqual(cards.fetch_avatar_bytes("https://avatars.example/avatar.png"), (cards.ASSETS / "profile-photo.png").read_bytes())

    def test_rendered_svgs_escape_labels_and_are_valid_xml(self):
        languages = Counter({"<script>": 9})
        overview = cards.render_overview_svg({}, [], languages, 12)
        activity = cards.render_activity_svg({"count": 4}, {"count": 12}, 365)
        language_card = cards.render_languages_svg(languages)
        self.assertIn("&lt;script&gt;", language_card)
        self.assertIn("CURRENT STREAK", activity)
        self.assertIn("LONGEST STREAK", activity)
        self.assertIn("CONTRIBUTIONS / 1 YEAR", activity)
        for svg in (overview, activity, language_card):
            self.assertTrue(svg.rstrip().endswith("</svg>"))
            ElementTree.fromstring(svg)

    def test_readme_and_workflow_have_no_conflict_markers(self):
        root = Path(__file__).resolve().parents[1]
        for path in (root / "README.md", root / ".github/workflows/update-profile-cards.yml", root / "scripts/update_profile_cards.py", root / "assets/github-activity.svg"):
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("<<<<<<<", content)
            self.assertNotIn(">>>>>>>", content)


if __name__ == "__main__":
    unittest.main()
