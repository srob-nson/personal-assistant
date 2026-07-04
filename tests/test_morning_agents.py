import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from personal_assistant.morning_agents import AgentSpec, run_agent


class MorningAgentTests(unittest.TestCase):
    def test_run_agent_uses_read_only_codex_exec_and_output_file(self):
        commands = []

        def fake_run(command, **kwargs):
            commands.append((command, kwargs))
            output_path = Path(command[command.index("--output-last-message") + 1])
            output_path.write_text("agent summary")
            return subprocess.CompletedProcess(command, 0)

        with tempfile.TemporaryDirectory() as temp_dir:
            spec = AgentSpec(
                name="repo",
                prompt="Inspect repo changes",
                workdir=Path("/tmp/example"),
                search_enabled=False,
            )

            with patch("personal_assistant.morning_agents.subprocess.run", fake_run):
                result = run_agent(spec, Path(temp_dir), timeout_seconds=12)

        command, kwargs = commands[0]
        self.assertEqual(command[:4], ["codex", "--ask-for-approval", "never", "exec"])
        self.assertIn("--output-last-message", command)
        self.assertNotIn("--search", command)
        self.assertEqual(kwargs["timeout"], 12)
        self.assertEqual(result.name, "repo")
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.summary, "agent summary")

    def test_run_agent_enables_search_only_when_requested(self):
        commands = []

        def fake_run(command, **kwargs):
            commands.append(command)
            output_path = Path(command[command.index("--output-last-message") + 1])
            output_path.write_text("weather summary")
            return subprocess.CompletedProcess(command, 0)

        with tempfile.TemporaryDirectory() as temp_dir:
            spec = AgentSpec(
                name="weather",
                prompt="Find weather",
                workdir=Path("/tmp/example"),
                search_enabled=True,
            )

            with patch("personal_assistant.morning_agents.subprocess.run", fake_run) as run:
                run_agent(spec, Path(temp_dir), timeout_seconds=12)

        self.assertEqual(commands[0][:5], ["codex", "--search", "--ask-for-approval", "never", "exec"])


if __name__ == "__main__":
    unittest.main()
