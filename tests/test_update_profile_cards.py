from collections import Counter
from datetime import date
import sys
import unittest
from xml.etree import ElementTree
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import update_profile_cards as cards


class ProfileCardTests(unittest.TestCase):
    def test_streaks_uses_latest_run_and_longest_run(self):
        days = [
            {"date": "2026-01-01", "contributionCount": 1},
            {"date": "2026-01-02", "contributionCount": 1},
            {"date": "2026-01-03", "contributionCount": 0},
            {"date": "2026-01-04", "contributionCount": 1},
        ]
        current, longest = cards.streaks(days)
        self.assertEqual(current["count"], 1)
        self.assertEqual(current["start"], date(2026, 1, 4))
        self.assertEqual(longest["count"], 2)

    def test_streaks_handles_no_contributions(self):
        current, longest = cards.streaks([{"date": "2026-01-01", "contributionCount": 0}])
        self.assertEqual(current["count"], 0)
        self.assertEqual(longest["count"], 0)

    def test_language_rows_are_sorted_and_limited(self):
        rows = cards.language_rows(Counter({"Python": 70, "JavaScript": 20, "HTML": 10, "CSS": 1, "Go": 1, "Rust": 1, "Java": 1}))
        self.assertEqual([row[0] for row in rows], ["Python", "JavaScript", "HTML", "CSS", "Go", "Rust"])
        self.assertAlmostEqual(rows[0][2], 67.307, places=2)

    def test_statistics_svg_escapes_language_names_and_closes_svg(self):
        stats = {"total": 12, "current": {"count": 2, "start": date(2026, 1, 2), "end": date(2026, 1, 3)}, "longest": {"count": 2, "start": date(2026, 1, 2), "end": date(2026, 1, 3)}, "commits": 5, "pull_requests": 3, "issues": 1, "repositories": 2}
        svg = cards.render_statistics_svg(stats, 4, Counter({"<script>": 9}))
        self.assertIn("&lt;script&gt;", svg)
        self.assertTrue(svg.rstrip().endswith("</svg>"))
        ElementTree.fromstring(svg)


if __name__ == "__main__":
    unittest.main()
