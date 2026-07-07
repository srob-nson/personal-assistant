import os
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

            with patch.dict(os.environ, {"PA_CODEX_COMMAND": "codex"}, clear=True):
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

            with patch.dict(os.environ, {"PA_CODEX_COMMAND": "codex"}, clear=True):
                with patch("personal_assistant.morning_agents.subprocess.run", fake_run) as run:
                    run_agent(spec, Path(temp_dir), timeout_seconds=12)

        self.assertEqual(commands[0][:5], ["codex", "--search", "--ask-for-approval", "never", "exec"])

    def test_run_agent_falls_back_to_home_local_codex_when_path_cannot_find_codex(self):
        commands = []

        def fake_run(command, **kwargs):
            commands.append(command)
            output_path = Path(command[command.index("--output-last-message") + 1])
            output_path.write_text("agent summary")
            return subprocess.CompletedProcess(command, 0)

        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir) / "home"
            codex_path = home / ".local" / "bin" / "codex"
            codex_path.parent.mkdir(parents=True)
            codex_path.write_text("")
            spec = AgentSpec(
                name="repo",
                prompt="Inspect repo changes",
                workdir=Path("/tmp/example"),
                search_enabled=False,
            )

            with patch.dict(os.environ, {"HOME": str(home), "PATH": "/usr/bin:/bin"}, clear=True):
                with patch("personal_assistant.morning_agents.subprocess.run", fake_run):
                    result = run_agent(spec, Path(temp_dir), timeout_seconds=12)

        self.assertEqual(commands[0][0], str(codex_path))
        self.assertEqual(result.status, "ok")

    def test_run_agent_uses_pa_codex_command_override(self):
        commands = []

        def fake_run(command, **kwargs):
            commands.append(command)
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

            with patch.dict(os.environ, {"PA_CODEX_COMMAND": "/opt/codex/bin/codex"}, clear=True):
                with patch("personal_assistant.morning_agents.subprocess.run", fake_run):
                    result = run_agent(spec, Path(temp_dir), timeout_seconds=12)

        self.assertEqual(commands[0][0], "/opt/codex/bin/codex")
        self.assertEqual(result.status, "ok")


if __name__ == "__main__":
    unittest.main()
