import os
import tempfile
import unittest
from pathlib import Path

from personal_assistant.codex_sessions import find_latest_codex_session_id


class CodexSessionTests(unittest.TestCase):
    def test_finds_newest_session_id_from_filename(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            sessions_dir = Path(temp_dir)
            older_id = "019f0e64-1111-7000-9000-111111111111"
            newer_id = "019f0e64-2222-7000-9000-222222222222"
            older = sessions_dir / f"rollout-2026-06-28T10-00-00-{older_id}.jsonl"
            newer = sessions_dir / f"rollout-2026-06-28T11-00-00-{newer_id}.jsonl"
            older.write_text("{}\n")
            newer.write_text("{}\n")
            os.utime(older, (1000, 1000))
            os.utime(newer, (2000, 2000))

            result = find_latest_codex_session_id(1500, sessions_dir=sessions_dir)

            self.assertEqual(result, newer_id)

    def test_finds_session_id_from_file_contents(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            sessions_dir = Path(temp_dir)
            session_id = "019f0e64-3333-7000-9000-333333333333"
            session_file = sessions_dir / "session.jsonl"
            session_file.write_text(f'{{"id": "{session_id}"}}\n')
            os.utime(session_file, (2000, 2000))

            result = find_latest_codex_session_id(1500, sessions_dir=sessions_dir)

            self.assertEqual(result, session_id)

    def test_returns_none_when_no_new_session_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            sessions_dir = Path(temp_dir)
            session_file = sessions_dir / "session.jsonl"
            session_file.write_text("{}\n")
            os.utime(session_file, (1000, 1000))

            result = find_latest_codex_session_id(1500, sessions_dir=sessions_dir)

            self.assertIsNone(result)

    def test_returns_none_when_sessions_dir_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            sessions_dir = Path(temp_dir) / "missing"

            result = find_latest_codex_session_id(1500, sessions_dir=sessions_dir)

            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
