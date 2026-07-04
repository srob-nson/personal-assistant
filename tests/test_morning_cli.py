import io
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import personal_assistant.cli as cli


class MorningCliTests(unittest.TestCase):
    def test_morning_rundown_dispatches_without_prompt_backend(self):
        calls = []

        def fake_morning(args):
            calls.append(args)
            return 0

        with patch.object(cli, "run_morning_rundown", fake_morning, create=True):
            with patch.object(cli, "run_codex") as run_codex:
                with patch.object(cli, "run_ollama") as run_ollama:
                    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                        result = cli.main(["pa", "morning-rundown"])

        self.assertEqual(result, 0)
        self.assertEqual(calls, [[]])
        run_codex.assert_not_called()
        run_ollama.assert_not_called()

    def test_morning_rundown_accepts_dry_run_and_force(self):
        calls = []

        def fake_morning(args):
            calls.append(args)
            return 0

        with patch.object(cli, "run_morning_rundown", fake_morning, create=True):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                result = cli.main(["pa", "morning-rundown", "--dry-run", "--force"])

        self.assertEqual(result, 0)
        self.assertEqual(calls, [["--dry-run", "--force"]])

    def test_invalid_morning_integer_env_does_not_break_help(self):
        env = dict(os.environ)
        env["PA_RUNDOWN_TASK_LIMIT"] = "many"
        env["PA_RUNDOWN_AGENT_TIMEOUT_SECONDS"] = "soon"
        pa_path = Path(__file__).resolve().parents[1] / "pa"

        result = subprocess.run(
            [sys.executable, str(pa_path), "--help"],
            text=True,
            capture_output=True,
            env=env,
            cwd=pa_path.parent,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Usage:", result.stdout)


if __name__ == "__main__":
    unittest.main()
