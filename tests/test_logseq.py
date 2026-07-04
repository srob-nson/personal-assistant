import io
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from personal_assistant.logseq import LogseqRecorder


def fixed_now():
    return datetime(2026, 6, 28, 12, 34, 56, tzinfo=timezone.utc)


class LogseqRecorderTests(unittest.TestCase):
    def make_recorder(self, graph_dir, stderr=None):
        return LogseqRecorder(
            graph_dir=graph_dir,
            username="sam",
            now_func=fixed_now,
            stderr=stderr,
        )

    def test_records_prompt_to_prompts_page(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            graph_dir = Path(temp_dir)
            recorder = self.make_recorder(graph_dir)

            recorder.record("prompt", "ollama", "hello", "pa-session-1", 1)

            prompts = graph_dir / "pages" / "Prompts.md"
            self.assertTrue(prompts.exists())
            text = prompts.read_text()
            self.assertIn("2026-06-28T12:34:56+00:00", text)
            self.assertIn("session `pa-session-1`", text)
            self.assertIn("turn `1`", text)
            self.assertIn("route `ollama`", text)
            self.assertIn("kind `prompt`", text)
            self.assertIn("user `sam`", text)
            self.assertIn("```text\n  hello\n  ```", text)

    def test_records_output_to_outputs_page_with_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            graph_dir = Path(temp_dir)
            recorder = self.make_recorder(graph_dir)

            recorder.record(
                "status",
                "codex",
                "Codex exited with status 0.",
                "pa-session-1",
                1,
                status="completed",
                metadata={
                    "exit_code": 0,
                    "codex_session_id": "019f0e64-293a-7e00-90b9-dca64817a56f",
                    "resume_command": "codex resume 019f0e64-293a-7e00-90b9-dca64817a56f",
                },
            )

            outputs = graph_dir / "pages" / "Outputs.md"
            text = outputs.read_text()
            self.assertIn("kind `status`", text)
            self.assertIn("status `completed`", text)
            self.assertIn("- exit_code:: 0", text)
            self.assertIn("- codex_session_id:: 019f0e64-293a-7e00-90b9-dca64817a56f", text)
            self.assertIn(
                "- resume_command:: `codex resume 019f0e64-293a-7e00-90b9-dca64817a56f`",
                text,
            )

    def test_uses_longer_fence_when_body_contains_backticks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            graph_dir = Path(temp_dir)
            recorder = self.make_recorder(graph_dir)

            recorder.record("output", "ollama", "```python\nprint('hi')\n```", "pa-1", 1)

            text = (graph_dir / "pages" / "Outputs.md").read_text()
            self.assertIn("````text", text)
            self.assertIn("  ```python", text)

    def test_missing_graph_root_warns_without_creating_graph(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            graph_dir = Path(temp_dir) / "missing"
            error = io.StringIO()
            recorder = self.make_recorder(graph_dir, stderr=error)

            recorder.record("prompt", "ollama", "hello", "pa-1", 1)

            self.assertFalse(graph_dir.exists())
            self.assertIn("Logseq capture disabled", error.getvalue())

    def test_append_starts_on_new_line_when_page_lacks_trailing_newline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            graph_dir = Path(temp_dir)
            pages_dir = graph_dir / "pages"
            pages_dir.mkdir()
            prompts = pages_dir / "Prompts.md"
            prompts.write_text("- existing")
            recorder = self.make_recorder(graph_dir)

            recorder.record("prompt", "ollama", "next", "pa-1", 1)

            text = prompts.read_text()
            self.assertIn("- existing\n- 2026-06-28T12:34:56+00:00", text)


if __name__ == "__main__":
    unittest.main()
