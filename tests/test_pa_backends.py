import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import personal_assistant.backends.codex as codex_backend
import personal_assistant.backends.ollama as ollama_backend
import personal_assistant.context as context_module


class FakeStreamResponse:
    def __init__(self, lines):
        self.lines = lines

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def raise_for_status(self):
        return None

    def iter_lines(self):
        return iter(self.lines)


class FakePostSequence:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if not self.responses:
            raise AssertionError("unexpected extra Ollama POST")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


class FakeRequestException(Exception):
    pass


def fake_requests_module(post):
    return SimpleNamespace(
        post=post,
        exceptions=SimpleNamespace(RequestException=FakeRequestException),
    )


def json_line(value):
    return json.dumps(value).encode("utf-8")


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


class BackendTests(unittest.TestCase):
    def call_run_codex(self, prompt="prompt", recorder=None, pa_session_id="pa-1"):
        output = io.StringIO()
        error = io.StringIO()
        kwargs = {}
        if recorder is not None:
            kwargs = {"recorder": recorder, "pa_session_id": pa_session_id}

        with redirect_stdout(output), redirect_stderr(error):
            try:
                result = codex_backend.run_codex(prompt, **kwargs)
            except Exception as exc:  # pragma: no cover - should be a test failure
                return None, output.getvalue(), error.getvalue(), exc

        return result, output.getvalue(), error.getvalue(), None

    def call_run_ollama(
        self,
        response_lines,
        prompt="prompt",
        followups=(),
        context="CTX::prompt",
        post=None,
        recorder=None,
        pa_session_id="pa-1",
    ):
        output = io.StringIO()
        error = io.StringIO()
        if post is None:
            post = FakePostSequence(
                [FakeStreamResponse(lines) for lines in response_lines]
            )
        fake_requests = fake_requests_module(post)
        input_mock = Mock(side_effect=followups)

        with patch.dict(sys.modules, {"requests": fake_requests}):
            with patch.object(
                ollama_backend,
                "build_ollama_system_prompt",
                lambda: context,
            ):
                with patch("builtins.input", input_mock):
                    with redirect_stdout(output), redirect_stderr(error):
                        try:
                            kwargs = {}
                            if recorder is not None:
                                kwargs = {
                                    "recorder": recorder,
                                    "pa_session_id": pa_session_id,
                                }
                            result = ollama_backend.run_ollama(prompt, **kwargs)
                        except Exception as exc:  # pragma: no cover - should be a test failure
                            return (
                                None,
                                output.getvalue(),
                                error.getvalue(),
                                exc,
                                post,
                                input_mock,
                            )

        return result, output.getvalue(), error.getvalue(), None, post, input_mock

    def call_run_ollama_with_lines(self, lines, prompt="prompt", followups=("exit",)):
        result, output, error, exc, _post, _input = self.call_run_ollama(
            [lines],
            prompt=prompt,
            followups=followups,
        )
        return result, output, error, exc

    def ollama_payloads(self, post):
        return [kwargs["json"] for _args, kwargs in post.calls]

    def message_contents(self, payload):
        return [(message["role"], message["content"]) for message in payload["messages"]]

    def assert_no_backend_exception(self, exc):
        self.assertIsNone(
            exc,
            f"backend should return an exit code instead of raising {type(exc).__name__}: {exc}",
        )

    def assert_concise_stderr(self, error):
        lines = [line for line in error.splitlines() if line.strip()]
        self.assertEqual(lines, [error.strip()])

    def with_temp_context_files(self, profile_text=None, memory_text=None, agents_text=None):
        temp_dir = tempfile.TemporaryDirectory()
        root = Path(temp_dir.name)
        profile_path = root / "profile.md"
        memory_path = root / "memory.md"
        agents_path = root / "AGENTS.md"

        if profile_text is not None:
            profile_path.write_text(profile_text, encoding="utf-8")
        if memory_text is not None:
            memory_path.write_text(memory_text, encoding="utf-8")
        if agents_text is not None:
            agents_path.write_text(agents_text, encoding="utf-8")

        return temp_dir, root, profile_path, memory_path, agents_path

    def test_run_codex_returns_subprocess_return_code(self):
        with patch.object(
            codex_backend.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=23),
        ) as run:
            result, _output, error, exc = self.call_run_codex()

        self.assert_no_backend_exception(exc)
        self.assertEqual(result, 23)
        self.assertEqual(error, "")
        run.assert_called_once_with(["codex", "prompt"], text=True)

    def test_run_codex_records_status_with_resume_command_when_available(self):
        recorder = FakeRecorder()
        codex_session_id = "019f0e64-293a-7e00-90b9-dca64817a56f"

        with patch.object(
            codex_backend.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=0),
        ):
            with patch.object(
                codex_backend,
                "find_latest_codex_session_id",
                return_value=codex_session_id,
            ):
                result, _output, error, exc = self.call_run_codex(recorder=recorder)

        self.assert_no_backend_exception(exc)
        self.assertEqual(result, 0)
        self.assertEqual(error, "")
        self.assertEqual(len(recorder.records), 1)
        record = recorder.records[0]
        self.assertEqual(record["kind"], "status")
        self.assertEqual(record["route"], "codex")
        self.assertEqual(record["session_id"], "pa-1")
        self.assertEqual(record["turn"], 1)
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["metadata"]["exit_code"], 0)
        self.assertEqual(record["metadata"]["codex_session_id"], codex_session_id)
        self.assertEqual(
            record["metadata"]["resume_command"],
            f"codex resume {codex_session_id}",
        )

    def test_run_codex_records_missing_command_status(self):
        recorder = FakeRecorder()

        with patch.object(codex_backend.subprocess, "run", side_effect=FileNotFoundError):
            result, _output, error, exc = self.call_run_codex(recorder=recorder)

        self.assert_no_backend_exception(exc)
        self.assertEqual(result, 127)
        self.assertIn("not found", error.lower())
        self.assertEqual(recorder.records[0]["kind"], "status")
        self.assertEqual(recorder.records[0]["status"], "command_not_found")

    def test_run_codex_returns_127_when_codex_command_is_missing(self):
        with patch.object(codex_backend.subprocess, "run", side_effect=FileNotFoundError):
            result, _output, error, exc = self.call_run_codex()

        self.assert_no_backend_exception(exc)
        self.assertEqual(result, 127)
        self.assert_concise_stderr(error)
        self.assertIn("codex", error.lower())
        self.assertIn("not found", error.lower())

    def test_run_codex_returns_1_when_subprocess_cannot_start(self):
        with patch.object(
            codex_backend.subprocess,
            "run",
            side_effect=OSError("permission denied"),
        ):
            result, _output, error, exc = self.call_run_codex()

        self.assert_no_backend_exception(exc)
        self.assertEqual(result, 1)
        self.assert_concise_stderr(error)
        self.assertIn("codex", error.lower())
        self.assertIn("permission denied", error.lower())

    def test_build_ollama_system_prompt_excludes_user_prompt_section(self):
        agents_file = Path.cwd() / "AGENTS.md"

        def fake_read_file(path):
            if path == context_module.PROFILE_FILE:
                return "PROFILE TEXT"
            if path == context_module.MEMORY_FILE:
                return "MEMORY TEXT"
            if path == agents_file:
                return "AGENTS TEXT"
            return ""

        with patch.object(context_module, "read_file", side_effect=fake_read_file):
            prompt = context_module.build_ollama_system_prompt()

        self.assertIn("PROFILE:\nPROFILE TEXT", prompt)
        self.assertIn("MEMORY:\nMEMORY TEXT", prompt)
        self.assertIn("PROJECT CONTEXT:\nAGENTS TEXT", prompt)
        self.assertNotIn("USER PROMPT:", prompt)

    def test_build_context_marks_missing_sources_without_truncation(self):
        temp_dir, root, profile_path, memory_path, agents_path = self.with_temp_context_files()
        self.addCleanup(temp_dir.cleanup)

        with patch.object(context_module, "PROFILE_FILE", profile_path):
            with patch.object(context_module, "MEMORY_FILE", memory_path):
                with patch.object(context_module.Path, "cwd", return_value=root):
                    prompt = context_module.build_context("hello")

        self.assertIn(f"[PROFILE | source={profile_path} | chars=0 | missing | full]", prompt)
        self.assertIn(f"[MEMORY | source={memory_path} | chars=0 | missing | full]", prompt)
        self.assertIn(
            f"[PROJECT CONTEXT | source={agents_path} | chars=0 | missing | full]",
            prompt,
        )
        self.assertIn("USER PROMPT:\nhello", prompt)

    def test_build_context_labels_sources_counts_and_truncation(self):
        temp_dir, root, profile_path, memory_path, agents_path = self.with_temp_context_files(
            profile_text="abcdef",
            memory_text="1234",
            agents_text="AGENTS BODY",
        )
        self.addCleanup(temp_dir.cleanup)

        with patch.object(context_module, "PROFILE_FILE", profile_path):
            with patch.object(context_module, "MEMORY_FILE", memory_path):
                with patch.object(context_module.Path, "cwd", return_value=root):
                    with patch.object(context_module, "CONTEXT_SECTION_CHAR_CAP", 4):
                        prompt = context_module.build_context("review this")
                        preview = context_module.build_context_preview("review this")

        self.assertIn(
            f"[PROFILE | source={profile_path} | chars=6 | present | truncated to 4]",
            prompt,
        )
        self.assertIn("abcd\n[TRUNCATED from 6 to 4 chars]", prompt)
        self.assertIn(
            f"[MEMORY | source={memory_path} | chars=4 | present | full]",
            prompt,
        )
        self.assertIn(
            f"[PROJECT CONTEXT | source={agents_path} | chars=11 | present | truncated to 4]",
            prompt,
        )
        self.assertIn("Codex shape:", preview)
        self.assertIn("Ollama shape:", preview)
        self.assertIn("USER PROMPT:\nreview this", preview)
        self.assertIn("role=system", preview)
        self.assertIn("role=user\nreview this", preview)

    def test_build_ollama_system_prompt_marks_truncated_sections(self):
        temp_dir, root, profile_path, memory_path, agents_path = self.with_temp_context_files(
            profile_text="abcdef",
            memory_text="123456",
            agents_text="xyz",
        )
        self.addCleanup(temp_dir.cleanup)

        with patch.object(context_module, "PROFILE_FILE", profile_path):
            with patch.object(context_module, "MEMORY_FILE", memory_path):
                with patch.object(context_module.Path, "cwd", return_value=root):
                    with patch.object(context_module, "CONTEXT_SECTION_CHAR_CAP", 3):
                        prompt = context_module.build_ollama_system_prompt()

        self.assertNotIn("USER PROMPT:", prompt)
        self.assertIn("[PROFILE | source=", prompt)
        self.assertIn("[TRUNCATED from 6 to 3 chars]", prompt)
        self.assertIn("[MEMORY | source=", prompt)
        self.assertIn("[TRUNCATED from 6 to 3 chars]", prompt)

    def test_run_ollama_first_payload_uses_context_system_and_raw_user_prompt(self):
        result, _output, error, exc, post, input_mock = self.call_run_ollama(
            [[json_line({"message": {"content": "hello"}, "done": True})]],
            prompt="raw prompt",
            context="CTX::raw prompt",
            followups=("exit",),
        )

        self.assert_no_backend_exception(exc)
        self.assertEqual(result, 0)
        self.assertEqual(error, "")
        input_mock.assert_called_once()
        payload = self.ollama_payloads(post)[0]
        messages = self.message_contents(payload)
        self.assertEqual(messages[0][0], "system")
        self.assertIn("CTX::raw prompt", messages[0][1])
        self.assertEqual(messages[1], ("user", "raw prompt"))
        self.assertEqual(len(messages), 2)

    def test_run_ollama_does_not_duplicate_context_into_user_messages(self):
        result, _output, _error, exc, post, _input_mock = self.call_run_ollama(
            [[json_line({"message": {"content": "hello"}, "done": True})]],
            prompt="raw prompt",
            context="CTX::raw prompt",
            followups=("exit",),
        )

        self.assert_no_backend_exception(exc)
        self.assertEqual(result, 0)
        for payload in self.ollama_payloads(post):
            for message in payload["messages"]:
                if message["role"] == "user":
                    self.assertNotIn("CTX::", message["content"])

    def test_run_ollama_second_request_includes_conversation_history(self):
        result, output, error, exc, post, _input_mock = self.call_run_ollama(
            [
                [json_line({"message": {"content": "first answer"}, "done": True})],
                [json_line({"message": {"content": "second answer"}, "done": True})],
            ],
            prompt="first prompt",
            context="CTX::first prompt",
            followups=("follow up", "exit"),
        )

        self.assert_no_backend_exception(exc)
        self.assertEqual(result, 0)
        self.assertEqual(error, "")
        self.assertIn("first answer", output)
        self.assertIn("second answer", output)
        payloads = self.ollama_payloads(post)
        self.assertEqual(len(payloads), 2)
        self.assertEqual(
            self.message_contents(payloads[1]),
            [
                ("system", "CTX::first prompt"),
                ("user", "first prompt"),
                ("assistant", "first answer"),
                ("user", "follow up"),
            ],
        )

    def test_run_ollama_records_successful_outputs_and_followup_prompts(self):
        recorder = FakeRecorder()

        result, output, error, exc, _post, _input_mock = self.call_run_ollama(
            [
                [json_line({"message": {"content": "first answer"}, "done": True})],
                [json_line({"message": {"content": "second answer"}, "done": True})],
            ],
            prompt="first prompt",
            followups=("follow up", "exit"),
            recorder=recorder,
            pa_session_id="pa-1",
        )

        self.assert_no_backend_exception(exc)
        self.assertEqual(result, 0)
        self.assertEqual(error, "")
        self.assertIn("first answer", output)
        self.assertEqual(
            [(record["kind"], record["turn"], record["body"]) for record in recorder.records],
            [
                ("output", 1, "first answer"),
                ("follow-up", 2, "follow up"),
                ("output", 2, "second answer"),
            ],
        )

    def test_run_ollama_records_failure_status_without_successful_output(self):
        recorder = FakeRecorder()
        post = FakePostSequence([FakeRequestException("boom")])

        result, _output, error, exc, _post, _input_mock = self.call_run_ollama(
            [],
            prompt="prompt",
            post=post,
            recorder=recorder,
            pa_session_id="pa-1",
        )

        self.assert_no_backend_exception(exc)
        self.assertEqual(result, 1)
        self.assertIn("Ollama request failed", error)
        self.assertEqual(len(recorder.records), 1)
        self.assertEqual(recorder.records[0]["kind"], "status")
        self.assertEqual(recorder.records[0]["status"], "request_failed")
        self.assertNotEqual(recorder.records[0]["kind"], "output")

    def test_run_ollama_exact_exit_after_first_response_skips_second_post(self):
        result, _output, error, exc, post, input_mock = self.call_run_ollama(
            [[json_line({"message": {"content": "hello"}, "done": True})]],
            followups=("exit",),
        )

        self.assert_no_backend_exception(exc)
        self.assertEqual(result, 0)
        self.assertEqual(error, "")
        input_mock.assert_called_once()
        self.assertEqual(len(post.calls), 1)

    def test_run_ollama_non_exact_exit_strings_are_followups(self):
        result, _output, error, exc, post, _input_mock = self.call_run_ollama(
            [
                [json_line({"message": {"content": "one"}, "done": True})],
                [json_line({"message": {"content": "two"}, "done": True})],
                [json_line({"message": {"content": "three"}, "done": True})],
            ],
            prompt="prompt",
            followups=("Exit", "exit ", "exit"),
        )

        self.assert_no_backend_exception(exc)
        self.assertEqual(result, 0)
        self.assertEqual(error, "")
        payloads = self.ollama_payloads(post)
        self.assertEqual(len(payloads), 3)
        self.assertEqual(payloads[1]["messages"][-1], {"role": "user", "content": "Exit"})
        self.assertEqual(payloads[2]["messages"][-1], {"role": "user", "content": "exit "})

    def test_run_ollama_empty_followups_reprompt_without_backend_call(self):
        result, _output, error, exc, post, input_mock = self.call_run_ollama(
            [
                [json_line({"message": {"content": "one"}, "done": True})],
                [json_line({"message": {"content": "two"}, "done": True})],
            ],
            prompt="prompt",
            followups=("", "   ", "follow up", "exit"),
        )

        self.assert_no_backend_exception(exc)
        self.assertEqual(result, 0)
        self.assertEqual(error, "")
        self.assertEqual(input_mock.call_count, 4)
        self.assertEqual(len(post.calls), 2)
        self.assertEqual(
            self.ollama_payloads(post)[1]["messages"][-1],
            {"role": "user", "content": "follow up"},
        )

    def test_run_ollama_eof_after_success_returns_0(self):
        result, _output, error, exc, post, input_mock = self.call_run_ollama(
            [[json_line({"message": {"content": "hello"}, "done": True})]],
            followups=(EOFError(),),
        )

        self.assert_no_backend_exception(exc)
        self.assertEqual(result, 0)
        self.assertEqual(error, "")
        input_mock.assert_called_once()
        self.assertEqual(len(post.calls), 1)

    def test_run_ollama_keyboard_interrupt_after_success_returns_130(self):
        result, _output, error, exc, post, _input_mock = self.call_run_ollama(
            [[json_line({"message": {"content": "hello"}, "done": True})]],
            followups=(KeyboardInterrupt(),),
        )

        self.assert_no_backend_exception(exc)
        self.assertEqual(result, 130)
        self.assertEqual(error, "Interrupted.\n")
        self.assertEqual(len(post.calls), 1)

    def test_run_ollama_keyboard_interrupt_during_stream_returns_130(self):
        post = FakePostSequence([KeyboardInterrupt()])

        result, _output, error, exc, _post, input_mock = self.call_run_ollama(
            [],
            prompt="prompt",
            followups=("exit",),
            post=post,
        )

        self.assert_no_backend_exception(exc)
        self.assertEqual(result, 130)
        self.assertEqual(error, "Interrupted.\n")
        input_mock.assert_not_called()
        self.assertEqual(len(post.calls), 1)

    def test_run_ollama_followup_backend_failure_returns_1(self):
        post = FakePostSequence(
            [
                FakeStreamResponse(
                    [json_line({"message": {"content": "hello"}, "done": True})]
                ),
                FakeRequestException("boom"),
            ]
        )

        result, _output, error, exc, _post, _input_mock = self.call_run_ollama(
            [],
            prompt="prompt",
            followups=("follow up",),
            post=post,
        )

        self.assert_no_backend_exception(exc)
        self.assertEqual(result, 1)
        self.assertIn("Ollama request failed", error)
        self.assertEqual(len(post.calls), 2)

    def test_run_ollama_accepts_valid_stream_response(self):
        result, output, error, exc = self.call_run_ollama_with_lines(
            [
                json_line({"message": {"content": "hel"}, "done": False}),
                json_line({"message": {"content": "lo"}, "done": True}),
            ]
        )

        self.assert_no_backend_exception(exc)
        self.assertEqual(result, 0)
        self.assertIn("hello", output)
        self.assertEqual(error, "")

    def test_run_ollama_rejects_malformed_stream_chunks(self):
        bad_chunks = [
            [],
            "ok",
            {"message": "text"},
            {"message": {"content": 123}},
        ]

        for chunk in bad_chunks:
            with self.subTest(chunk=chunk):
                result, _output, error, exc = self.call_run_ollama_with_lines(
                    [json_line(chunk)]
                )

                self.assert_no_backend_exception(exc)
                self.assertEqual(result, 1)
                self.assertIn("malformed", error.lower())
                self.assertIn("stream", error.lower())

    def test_run_ollama_invalid_json_returns_1(self):
        result, _output, error, exc = self.call_run_ollama_with_lines([b"{"])

        self.assert_no_backend_exception(exc)
        self.assertEqual(result, 1)
        self.assertIn("Ollama returned invalid JSON", error)

    def test_run_ollama_request_exception_returns_1(self):
        output = io.StringIO()
        error = io.StringIO()
        request_error = FakeRequestException("boom")
        fake_requests = fake_requests_module(Mock(side_effect=request_error))

        with patch.dict(sys.modules, {"requests": fake_requests}):
            with redirect_stdout(output), redirect_stderr(error):
                result = ollama_backend.run_ollama("prompt")

        self.assertEqual(result, 1)
        self.assertIn("Ollama request failed", error.getvalue())

    def test_run_ollama_stream_ending_before_done_returns_1(self):
        result, _output, error, exc = self.call_run_ollama_with_lines(
            [json_line({"message": {"content": "hello"}, "done": False})]
        )

        self.assert_no_backend_exception(exc)
        self.assertEqual(result, 1)
        self.assertIn("Ollama stream ended before completion.", error)


if __name__ == "__main__":
    unittest.main()
