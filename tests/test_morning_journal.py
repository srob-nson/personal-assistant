import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from personal_assistant.morning_journal import (
    build_journal_block,
    journal_path_for_date,
    upsert_journal_block,
)


class MorningJournalTests(unittest.TestCase):
    def test_journal_path_uses_logseq_default_date_filename(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            graph_dir = Path(temp_dir)

            path = journal_path_for_date(graph_dir, date(2026, 6, 30))

            self.assertEqual(path, graph_dir / "journals" / "2026_06_30.md")

    def test_upsert_replaces_only_existing_generated_block(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            journal = Path(temp_dir) / "journals" / "2026_06_30.md"
            journal.parent.mkdir()
            journal.write_text("- existing note\n<!-- pa-morning-rundown:start 2026-06-30 -->\nold\n<!-- pa-morning-rundown:end 2026-06-30 -->\n- keep me\n")
            block = build_journal_block(
                run_date=date(2026, 6, 30),
                generated_at=datetime(2026, 6, 30, 6, 0, tzinfo=timezone.utc),
                tasks=["TODO Review [[Goals]] and pick the next concrete action"],
                source_statuses=["logseq ok", "repo ok"],
            )

            upsert_journal_block(journal, date(2026, 6, 30), block, force=True)

            text = journal.read_text()
            self.assertIn("- existing note", text)
            self.assertIn("- keep me", text)
            self.assertNotIn("old", text)
            self.assertIn("pa_morning_rundown:: 2026-06-30", text)
            self.assertIn("TODO Review [[Goals]]", text)

    def test_upsert_skips_existing_block_without_force(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            journal = Path(temp_dir) / "journals" / "2026_06_30.md"
            journal.parent.mkdir()
            original = "<!-- pa-morning-rundown:start 2026-06-30 -->\nold\n<!-- pa-morning-rundown:end 2026-06-30 -->\n"
            journal.write_text(original)

            wrote = upsert_journal_block(
                journal,
                date(2026, 6, 30),
                "new",
                force=False,
            )

            self.assertFalse(wrote)
            self.assertEqual(journal.read_text(), original)


if __name__ == "__main__":
    unittest.main()
