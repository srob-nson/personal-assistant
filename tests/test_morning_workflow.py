import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from personal_assistant.morning import run_morning_rundown
from personal_assistant.morning_agents import AgentResult


class MorningWorkflowTests(unittest.TestCase):
    def test_dry_run_prints_rundown_without_writing_journal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            graph_dir = Path(temp_dir)
            (graph_dir / "pages").mkdir()
            (graph_dir / "pages" / "Goals.md").write_text("- TODO Ship morning brief\n")
            (graph_dir / "pages" / "Tasks.md").write_text("- TODO Review cron plan\n")
            (graph_dir / "pages" / "Projects.md").write_text("- [[Personal Assistant]]\n")
            output = []

            def fake_run_agents(specs, run_dir, timeout_seconds):
                names = [spec.name for spec in specs]
                if names == ["reviewer"]:
                    return [AgentResult("reviewer", "ok", "- TODO Write one focused task", 0)]
                return [
                    AgentResult(name, "ok", f"{name} summary", 0)
                    for name in names
                ]

            with patch("personal_assistant.morning.LOGSEQ_GRAPH_DIR", graph_dir):
                with patch("personal_assistant.morning.RUNDOWN_WEATHER_LOCATION", ""):
                    with patch("personal_assistant.morning.run_agents", fake_run_agents):
                        result = run_morning_rundown(
                            ["--dry-run"],
                            today_func=lambda: date(2026, 6, 30),
                            now_func=lambda: datetime(2026, 6, 30, 6, 0, tzinfo=timezone.utc),
                            stdout=output.append,
                        )

            self.assertEqual(result, 0)
            self.assertIn("TODO Write one focused task", "\n".join(output))
            self.assertFalse((graph_dir / "journals" / "2026_06_30.md").exists())

    def test_successful_run_writes_today_journal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            graph_dir = Path(temp_dir)
            (graph_dir / "pages").mkdir()
            (graph_dir / "pages" / "Goals.md").write_text("- TODO Ship morning brief\n")
            (graph_dir / "pages" / "Tasks.md").write_text("- TODO Review cron plan\n")
            (graph_dir / "pages" / "Projects.md").write_text("- [[Personal Assistant]]\n")

            def fake_run_agents(specs, run_dir, timeout_seconds):
                names = [spec.name for spec in specs]
                if names == ["reviewer"]:
                    return [AgentResult("reviewer", "ok", "- TODO Write one focused task", 0)]
                return [
                    AgentResult(name, "ok", f"{name} summary", 0)
                    for name in names
                ]

            with patch("personal_assistant.morning.LOGSEQ_GRAPH_DIR", graph_dir):
                with patch("personal_assistant.morning.RUNDOWN_WEATHER_LOCATION", "London"):
                    with patch(
                        "personal_assistant.morning.fetch_weather_summary",
                        return_value=AgentResult(
                            "weather",
                            "ok",
                            "- Whole Day: 13 C to 22 C.\n- Light: sunrise 05:00, sunset 21:10.",
                            0,
                        ),
                    ):
                        with patch("personal_assistant.morning.run_agents", fake_run_agents):
                            result = run_morning_rundown(
                                [],
                                today_func=lambda: date(2026, 6, 30),
                                now_func=lambda: datetime(2026, 6, 30, 6, 0, tzinfo=timezone.utc),
                                stdout=lambda _message: None,
                            )

            self.assertEqual(result, 0)
            journal = graph_dir / "journals" / "2026_06_30.md"
            text = journal.read_text()
            self.assertIn("pa_morning_rundown:: 2026-06-30", text)
            self.assertIn("TODO Write one focused task", text)
            self.assertIn("source_status:: logseq ok; repo ok; news ok; weather ok; reviewer ok", text)
            self.assertIn("  - Weather", text)
            self.assertIn("    - Whole Day: 13 C to 22 C.", text)
            self.assertIn("    - Light: sunrise 05:00, sunset 21:10.", text)
            self.assertNotIn("Current:", text)

    def test_default_generated_at_includes_timezone_offset(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            graph_dir = Path(temp_dir)
            (graph_dir / "pages").mkdir()
            (graph_dir / "pages" / "Goals.md").write_text("- TODO Ship morning brief\n")

            def fake_run_agents(specs, run_dir, timeout_seconds):
                names = [spec.name for spec in specs]
                if names == ["reviewer"]:
                    return [AgentResult("reviewer", "ok", "- TODO Write one focused task", 0)]
                return [
                    AgentResult(name, "ok", f"{name} summary", 0)
                    for name in names
                ]

            with patch("personal_assistant.morning.LOGSEQ_GRAPH_DIR", graph_dir):
                with patch("personal_assistant.morning.RUNDOWN_WEATHER_LOCATION", ""):
                    with patch("personal_assistant.morning.run_agents", fake_run_agents):
                        result = run_morning_rundown(
                            [],
                            today_func=lambda: date(2026, 6, 30),
                            stdout=lambda _message: None,
                        )

            self.assertEqual(result, 0)
            text = (graph_dir / "journals" / "2026_06_30.md").read_text()
            self.assertRegex(text, r"generated_at:: .*[+-][0-9]{2}:[0-9]{2}")

    def test_existing_marker_skips_before_running_agents(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            graph_dir = Path(temp_dir)
            (graph_dir / "pages").mkdir()
            (graph_dir / "pages" / "Goals.md").write_text("- TODO Ship morning brief\n")
            journal = graph_dir / "journals" / "2026_06_30.md"
            journal.parent.mkdir()
            journal.write_text(
                "<!-- pa-morning-rundown:start 2026-06-30 -->\n"
                "old\n"
                "<!-- pa-morning-rundown:end 2026-06-30 -->\n"
            )

            def fail_run_agents(specs, run_dir, timeout_seconds):
                raise AssertionError("agents should not run when today's marker exists")

            with patch("personal_assistant.morning.LOGSEQ_GRAPH_DIR", graph_dir):
                with patch("personal_assistant.morning.run_agents", fail_run_agents):
                    result = run_morning_rundown(
                        [],
                        today_func=lambda: date(2026, 6, 30),
                        stdout=lambda _message: None,
                    )

            self.assertEqual(result, 0)
            self.assertIn("old", journal.read_text())

    def test_missing_weather_location_does_not_launch_weather_agent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            graph_dir = Path(temp_dir)
            (graph_dir / "pages").mkdir()
            (graph_dir / "pages" / "Goals.md").write_text("- TODO Ship morning brief\n")
            source_batches = []

            def fake_run_agents(specs, run_dir, timeout_seconds):
                names = [spec.name for spec in specs]
                source_batches.append(names)
                if names == ["reviewer"]:
                    return [AgentResult("reviewer", "ok", "- TODO Write one focused task", 0)]
                return [
                    AgentResult(name, "ok", f"{name} summary", 0)
                    for name in names
                ]

            with patch("personal_assistant.morning.LOGSEQ_GRAPH_DIR", graph_dir):
                with patch("personal_assistant.morning.RUNDOWN_WEATHER_LOCATION", ""):
                    with patch("personal_assistant.morning.run_agents", fake_run_agents):
                        result = run_morning_rundown(
                            [],
                            today_func=lambda: date(2026, 6, 30),
                            now_func=lambda: datetime(2026, 6, 30, 6, 0, tzinfo=timezone.utc),
                            stdout=lambda _message: None,
                        )

            self.assertEqual(result, 0)
            self.assertNotIn("weather", source_batches[0])
            text = (graph_dir / "journals" / "2026_06_30.md").read_text()
            self.assertIn("weather unavailable", text)

    def test_weather_location_uses_weather_api_instead_of_agent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            graph_dir = Path(temp_dir)
            (graph_dir / "pages").mkdir()
            (graph_dir / "pages" / "Goals.md").write_text("- TODO Ship morning brief\n")
            source_batches = []
            weather_calls = []

            def fake_run_agents(specs, run_dir, timeout_seconds):
                names = [spec.name for spec in specs]
                source_batches.append(names)
                if names == ["reviewer"]:
                    return [AgentResult("reviewer", "ok", "- TODO Write one focused task", 0)]
                return [
                    AgentResult(name, "ok", f"{name} summary", 0)
                    for name in names
                ]

            def fake_fetch_weather(location, timeout_seconds):
                weather_calls.append((location, timeout_seconds))
                return AgentResult("weather", "ok", "weather summary", 0)

            with patch("personal_assistant.morning.LOGSEQ_GRAPH_DIR", graph_dir):
                with patch("personal_assistant.morning.RUNDOWN_WEATHER_LOCATION", "London"):
                    with patch("personal_assistant.morning.RUNDOWN_WEATHER_TIMEOUT_SECONDS", 7):
                        with patch("personal_assistant.morning.fetch_weather_summary", fake_fetch_weather):
                            with patch("personal_assistant.morning.run_agents", fake_run_agents):
                                result = run_morning_rundown(
                                    [],
                                    today_func=lambda: date(2026, 6, 30),
                                    now_func=lambda: datetime(2026, 6, 30, 6, 0, tzinfo=timezone.utc),
                                    stdout=lambda _message: None,
                                )

            self.assertEqual(result, 0)
            self.assertEqual(source_batches[0], ["logseq", "repo", "news"])
            self.assertEqual(weather_calls, [("London", 7)])

    def test_weather_failure_writes_journal_and_returns_degraded_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            graph_dir = Path(temp_dir)
            (graph_dir / "pages").mkdir()
            (graph_dir / "pages" / "Goals.md").write_text("- TODO Ship morning brief\n")
            errors = []

            def fake_run_agents(specs, run_dir, timeout_seconds):
                names = [spec.name for spec in specs]
                if names == ["reviewer"]:
                    return [AgentResult("reviewer", "ok", "- TODO Write one focused task", 0)]
                return [
                    AgentResult(name, "ok", f"{name} summary", 0)
                    for name in names
                ]

            with patch("personal_assistant.morning.LOGSEQ_GRAPH_DIR", graph_dir):
                with patch("personal_assistant.morning.RUNDOWN_WEATHER_LOCATION", "London"):
                    with patch(
                        "personal_assistant.morning.fetch_weather_summary",
                        return_value=AgentResult("weather", "failed", "weather API failed", 1),
                    ):
                        with patch("personal_assistant.morning.run_agents", fake_run_agents):
                            result = run_morning_rundown(
                                [],
                                today_func=lambda: date(2026, 6, 30),
                                now_func=lambda: datetime(2026, 6, 30, 6, 0, tzinfo=timezone.utc),
                                stdout=lambda _message: None,
                                stderr=errors.append,
                            )

            self.assertEqual(result, 1)
            text = (graph_dir / "journals" / "2026_06_30.md").read_text()
            self.assertIn("source_status:: logseq ok; repo ok; news ok; weather failed; reviewer ok", text)
            self.assertEqual(errors, ["Morning rundown degraded: weather failed"])

    def test_reviewer_detailed_tasks_are_capped_at_five_and_preserve_details(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            graph_dir = Path(temp_dir)
            (graph_dir / "pages").mkdir()
            (graph_dir / "pages" / "Goals.md").write_text("- TODO Ship morning brief\n")
            output = []
            reviewer_summary = "\n".join(
                [
                    f"- TODO Focused outcome {index}"
                    f"\n  source:: [[Projects]]"
                    f"\n  why:: Reason {index}"
                    f"\n  next:: Action {index}"
                    for index in range(1, 7)
                ]
            )

            def fake_run_agents(specs, run_dir, timeout_seconds):
                names = [spec.name for spec in specs]
                if names == ["reviewer"]:
                    return [AgentResult("reviewer", "ok", reviewer_summary, 0)]
                return [
                    AgentResult(name, "ok", f"{name} summary", 0)
                    for name in names
                ]

            with patch("personal_assistant.morning.LOGSEQ_GRAPH_DIR", graph_dir):
                with patch("personal_assistant.morning.RUNDOWN_WEATHER_LOCATION", ""):
                    with patch("personal_assistant.morning.RUNDOWN_TASK_LIMIT", 5):
                        with patch("personal_assistant.morning.run_agents", fake_run_agents):
                            result = run_morning_rundown(
                                ["--dry-run"],
                                today_func=lambda: date(2026, 6, 30),
                                now_func=lambda: datetime(2026, 6, 30, 6, 0, tzinfo=timezone.utc),
                                stdout=output.append,
                            )

            block = "\n".join(output)
            self.assertEqual(result, 0)
            self.assertEqual(block.count("  - TODO Focused outcome"), 5)
            self.assertIn(
                "  - TODO Focused outcome 1\n"
                "    source:: [[Projects]]\n"
                "    why:: Reason 1\n"
                "    next:: Action 1",
                block,
            )
            self.assertIn("  - TODO Focused outcome 5", block)
            self.assertIn("    next:: Action 5", block)
            self.assertNotIn("Focused outcome 6", block)
            self.assertNotIn("Action 6", block)


if __name__ == "__main__":
    unittest.main()
