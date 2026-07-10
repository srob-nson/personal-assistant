import io
import importlib
import tempfile
import unittest
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import personal_assistant.context as context_module
import personal_assistant.cli as cli


@contextmanager
def requests_import_unavailable():
    real_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "requests" or name.startswith("requests."):
            raise ModuleNotFoundError("No module named 'requests'")
        return real_import(name, globals, locals, fromlist, level)

    with patch("builtins.__import__", side_effect=fake_import):
        yield


def install_fake_backends():
    calls = []

    def fake_codex(prompt, **kwargs):
        calls.append(("codex", prompt, kwargs))
        return 0

    def fake_ollama(prompt, **kwargs):
        calls.append(("ollama", prompt, kwargs))
        return 0

    return calls, fake_codex, fake_ollama


class FakeRecorder:
    def __init__(self):
        self.records = []

    def record(self, kind, route, body, session_id, turn, status=None, metadata=None):
        self.records.append(
            {
                "kind": kind,
                "route": route,
                "body": body,
                "session_id": session_id,
                "turn": turn,
                "status": status,
                "metadata": metadata or {},
            }
        )


class RoutingTests(unittest.TestCase):
    def run_pa(self, argv, recorder=None):
        calls, fake_codex, fake_ollama = install_fake_backends()
        if recorder is None:
            recorder = FakeRecorder()

        output = io.StringIO()
        error = io.StringIO()

        with patch.object(cli, "run_codex", fake_codex):
            with patch.object(cli, "run_ollama", fake_ollama):
                with patch.object(cli, "build_context", lambda prompt: f"CTX::{prompt}"):
                    with patch.object(
                        cli,
                        "build_context_preview",
                        lambda prompt: f"PREVIEW::{prompt}",
                        create=True,
                    ):
                        with patch.object(
                            cli,
                            "LogseqRecorder",
                            return_value=recorder,
                            create=True,
                    ):
                            with patch.object(
                                cli,
                                "new_session_id",
                                return_value="pa-session-1",
                                create=True,
                            ):
                                with redirect_stdout(output), redirect_stderr(error):
                                    result = cli.main(argv)

        return result, calls, recorder, output.getvalue(), error.getvalue()

    def call_summary(self, calls):
        return [(route, prompt) for route, prompt, _kwargs in calls]

    def test_codex_flag_forces_codex_for_non_coding_prompt(self):
        result, calls, _recorder, _output, _error = self.run_pa(["pa", "-c", "hello"])

        self.assertEqual(result, 0)
        self.assertEqual(self.call_summary(calls), [("codex", "CTX::hello")])

    def test_ollama_flag_forces_ollama_for_coding_prompt(self):
        result, calls, _recorder, _output, _error = self.run_pa(
            ["pa", "-o", "review", "this", "repository"]
        )

        self.assertEqual(result, 0)
        self.assertEqual(self.call_summary(calls), [("ollama", "review this repository")])

    def test_default_keyword_routing_still_uses_codex_for_coding_prompt(self):
        result, calls, _recorder, _output, _error = self.run_pa(
            ["pa", "review", "this", "repository"]
        )

        self.assertEqual(result, 0)
        self.assertEqual(self.call_summary(calls), [("codex", "CTX::review this repository")])

    def test_default_keyword_routing_still_uses_ollama_for_general_prompt(self):
        result, calls, _recorder, _output, _error = self.run_pa(["pa", "hello"])

        self.assertEqual(result, 0)
        self.assertEqual(self.call_summary(calls), [("ollama", "hello")])

    def test_forced_route_without_prompt_prints_usage_and_fails(self):
        for flag in ("-c", "-o", "-l"):
            calls, fake_codex, fake_ollama = install_fake_backends()
            output = io.StringIO()

            with self.subTest(flag=flag):
                with patch.object(cli, "run_codex", fake_codex):
                    with patch.object(cli, "run_ollama", fake_ollama):
                        with redirect_stdout(output):
                            result = cli.main(["pa", flag])

                self.assertEqual(result, 1)
                self.assertEqual(calls, [])
                self.assertIn("Usage:", output.getvalue())

    def test_logseq_flag_records_initial_prompt_before_codex_route(self):
        recorder = FakeRecorder()

        result, calls, _recorder, _output, _error = self.run_pa(
            ["pa", "-l", "-c", "hello"], recorder
        )

        self.assertEqual(result, 0)
        self.assertEqual(self.call_summary(calls), [("codex", "CTX::hello")])
        self.assertEqual(calls[0][2]["recorder"], recorder)
        self.assertEqual(calls[0][2]["pa_session_id"], "pa-session-1")
        self.assertEqual(
            recorder.records,
            [
                {
                    "kind": "prompt",
                    "route": "codex",
                    "body": "hello",
                    "session_id": "pa-session-1",
                    "turn": 1,
                    "status": None,
                    "metadata": {},
                }
            ],
        )

    def test_logseq_flag_records_initial_prompt_before_ollama_route(self):
        recorder = FakeRecorder()

        result, calls, _recorder, _output, _error = self.run_pa(
            ["pa", "-o", "-l", "hello"], recorder
        )

        self.assertEqual(result, 0)
        self.assertEqual(self.call_summary(calls), [("ollama", "hello")])
        self.assertEqual(calls[0][2]["recorder"], recorder)
        self.assertEqual(calls[0][2]["pa_session_id"], "pa-session-1")
        self.assertEqual(recorder.records[0]["route"], "ollama")
        self.assertEqual(recorder.records[0]["body"], "hello")

    def test_conflicting_route_flags_print_usage_and_fail(self):
        for argv in (["pa", "-c", "-o", "hello"], ["pa", "-o", "-c", "hello"]):
            with self.subTest(argv=argv):
                result, calls, recorder, _output, _error = self.run_pa(argv)

                self.assertEqual(result, 1)
                self.assertEqual(calls, [])
                self.assertEqual(recorder.records, [])

    def test_old_long_route_flags_print_usage_and_fail(self):
        for flag in ("--codex", "--ollama"):
            with self.subTest(flag=flag):
                result, calls, recorder, _output, _error = self.run_pa(["pa", flag, "hello"])

                self.assertEqual(result, 1)
                self.assertEqual(calls, [])
                self.assertEqual(recorder.records, [])

    def test_unknown_leading_flag_prints_usage_and_fails(self):
        result, calls, recorder, _output, _error = self.run_pa(["pa", "-x", "hello"])

        self.assertEqual(result, 1)
        self.assertEqual(calls, [])
        self.assertEqual(recorder.records, [])

    def test_flags_after_prompt_are_prompt_text(self):
        result, calls, _recorder, _output, _error = self.run_pa(["pa", "hello", "-l"])

        self.assertEqual(result, 0)
        self.assertEqual(self.call_summary(calls), [("ollama", "hello -l")])

    def test_module_loads_and_help_runs_without_requests_dependency(self):
        output = io.StringIO()

        with requests_import_unavailable():
            try:
                importlib.reload(cli)
            except ModuleNotFoundError as exc:
                self.fail(f"personal_assistant.cli should load without requests installed: {exc}")

            with redirect_stdout(output):
                result = cli.main(["pa", "--help"])

        self.assertEqual(result, 0)
        self.assertIn("Usage:", output.getvalue())

    def test_codex_routed_fake_backend_works_without_requests_dependency(self):
        with requests_import_unavailable():
            try:
                importlib.reload(cli)
            except ModuleNotFoundError as exc:
                self.fail(f"Codex routing should not require requests: {exc}")

            calls, fake_codex, fake_ollama = install_fake_backends()

            with patch.object(cli, "run_codex", fake_codex):
                with patch.object(cli, "run_ollama", fake_ollama):
                    with patch.object(cli, "build_context", lambda prompt: f"CTX::{prompt}"):
                        result = cli.main(["pa", "review", "this", "repository"])

        self.assertEqual(result, 0)
        self.assertEqual(
            [(route, prompt) for route, prompt, _kwargs in calls],
            [("codex", "CTX::review this repository")],
        )

    def test_context_preview_prints_preview_without_calling_backends(self):
        result, calls, recorder, output, error = self.run_pa(
            ["pa", "--context-preview", "review", "this", "repository"]
        )

        self.assertEqual(result, 0)
        self.assertEqual(calls, [])
        self.assertEqual(recorder.records, [])
        self.assertEqual(error, "")
        self.assertEqual(output.strip(), "PREVIEW::review this repository")

    def test_context_preview_without_prompt_prints_usage_and_fails(self):
        result, calls, recorder, output, error = self.run_pa(["pa", "--context-preview"])

        self.assertEqual(result, 1)
        self.assertEqual(calls, [])
        self.assertEqual(recorder.records, [])
        self.assertEqual(error, "")
        self.assertIn("Usage:", output)

    def test_context_preview_rejects_route_flags_without_prompt(self):
        result, calls, recorder, output, _error = self.run_pa(["pa", "--context-preview", "-c"])

        self.assertEqual(result, 1)
        self.assertEqual(calls, [])
        self.assertEqual(recorder.records, [])
        self.assertIn("Usage:", output)

    def test_context_preview_prints_real_shapes_without_backends_or_logseq(self):
        calls, fake_codex, fake_ollama = install_fake_backends()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = root / "profile.md"
            memory_path = root / "memory.md"
            agents_path = root / "AGENTS.md"
            profile_path.write_text("abcdef", encoding="utf-8")
            memory_path.write_text("memo", encoding="utf-8")
            agents_path.write_text("AGENTS BODY", encoding="utf-8")

            output = io.StringIO()
            error = io.StringIO()

            with patch.object(context_module, "PROFILE_FILE", profile_path):
                with patch.object(context_module, "MEMORY_FILE", memory_path):
                    with patch.object(context_module.Path, "cwd", return_value=root):
                        with patch.object(context_module, "CONTEXT_SECTION_CHAR_CAP", 5):
                            with patch.object(context_module, "CONTEXT_PROFILE_CHAR_CAP", 5):
                                with patch.object(context_module, "CONTEXT_MEMORY_CHAR_CAP", 5):
                                    with patch.object(context_module, "CONTEXT_AGENTS_CHAR_CAP", 5):
                                        with patch.object(cli, "run_codex", fake_codex):
                                            with patch.object(cli, "run_ollama", fake_ollama):
                                                with patch.object(
                                                    cli,
                                                    "LogseqRecorder",
                                                    side_effect=AssertionError(
                                                        "preview should not capture Logseq"
                                                    ),
                                                ):
                                                    with redirect_stdout(output):
                                                        with redirect_stderr(error):
                                                            result = cli.main(
                                                                [
                                                                    "pa",
                                                                    "--context-preview",
                                                                    "-l",
                                                                    "hello",
                                                                ]
                                                            )

        preview = output.getvalue()
        self.assertEqual(result, 0)
        self.assertEqual(calls, [])
        self.assertEqual(error.getvalue(), "")
        self.assertIn("Codex shape:", preview)
        self.assertIn("USER PROMPT:\nhello", preview)
        self.assertIn("Ollama shape:", preview)
        self.assertIn("role=system", preview)
        self.assertIn("role=user\nhello", preview)
        self.assertIn(
            f"[PROFILE | source={profile_path} | chars=6 | present | truncated to 5]",
            preview,
        )
        self.assertIn(
            f"[MEMORY | source={memory_path} | chars=4 | present | full]",
            preview,
        )
        self.assertIn(
            f"[PROJECT CONTEXT | source={agents_path} | chars=11 | present | truncated to 5]",
            preview,
        )
        self.assertIn("[TRUNCATED from 6 to 5 chars]", preview)

    def test_run_ollama_reports_missing_requests_dependency(self):
        import personal_assistant.backends.ollama as ollama_backend

        error = io.StringIO()

        with requests_import_unavailable():
            try:
                importlib.reload(ollama_backend)
            except ModuleNotFoundError as exc:
                self.fail(f"Ollama backend should load before reporting dependency errors: {exc}")

            with redirect_stderr(error):
                try:
                    result = ollama_backend.run_ollama("prompt")
                except ModuleNotFoundError as exc:
                    self.fail(f"run_ollama should report missing requests cleanly: {exc}")

        self.assertEqual(result, 1)
        self.assertEqual(
            error.getvalue().strip(),
            "Ollama backend requires the Python package 'requests'.",
        )


if __name__ == "__main__":
    unittest.main()
