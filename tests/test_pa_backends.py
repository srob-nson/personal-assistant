import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


REPO_ROOT = Path(__file__).resolve().parents[1]
PA_PATH = REPO_ROOT / "bin" / "pa"


def load_pa_module():
    loader = SourceFileLoader("pa_under_test", str(PA_PATH))
    spec = spec_from_loader(loader.name, loader)
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


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


class FakeRequestException(Exception):
    pass


def fake_requests_module(post):
    return SimpleNamespace(
        post=post,
        exceptions=SimpleNamespace(RequestException=FakeRequestException),
    )


def json_line(value):
    return json.dumps(value).encode("utf-8")


class BackendTests(unittest.TestCase):
    def call_run_codex(self, pa_module, prompt="prompt"):
        output = io.StringIO()
        error = io.StringIO()

        with redirect_stdout(output), redirect_stderr(error):
            try:
                result = pa_module.run_codex(prompt)
            except Exception as exc:  # pragma: no cover - should be a test failure
                return None, output.getvalue(), error.getvalue(), exc

        return result, output.getvalue(), error.getvalue(), None

    def call_run_ollama_with_lines(self, lines, prompt="prompt"):
        output = io.StringIO()
        error = io.StringIO()
        post = Mock(return_value=FakeStreamResponse(lines))
        fake_requests = fake_requests_module(post)

        with patch.dict(sys.modules, {"requests": fake_requests}):
            pa_module = load_pa_module()
            with redirect_stdout(output), redirect_stderr(error):
                try:
                    result = pa_module.run_ollama(prompt)
                except Exception as exc:  # pragma: no cover - should be a test failure
                    return None, output.getvalue(), error.getvalue(), exc

        return result, output.getvalue(), error.getvalue(), None

    def assert_no_backend_exception(self, exc):
        self.assertIsNone(
            exc,
            f"backend should return an exit code instead of raising {type(exc).__name__}: {exc}",
        )

    def assert_concise_stderr(self, error):
        lines = [line for line in error.splitlines() if line.strip()]
        self.assertEqual(lines, [error.strip()])

    def test_run_codex_returns_subprocess_return_code(self):
        pa_module = load_pa_module()

        with patch.object(
            pa_module.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=23),
        ) as run:
            result, _output, error, exc = self.call_run_codex(pa_module)

        self.assert_no_backend_exception(exc)
        self.assertEqual(result, 23)
        self.assertEqual(error, "")
        run.assert_called_once_with(["codex", "prompt"], text=True)

    def test_run_codex_returns_127_when_codex_command_is_missing(self):
        pa_module = load_pa_module()

        with patch.object(pa_module.subprocess, "run", side_effect=FileNotFoundError):
            result, _output, error, exc = self.call_run_codex(pa_module)

        self.assert_no_backend_exception(exc)
        self.assertEqual(result, 127)
        self.assert_concise_stderr(error)
        self.assertIn("codex", error.lower())
        self.assertIn("not found", error.lower())

    def test_run_codex_returns_1_when_subprocess_cannot_start(self):
        pa_module = load_pa_module()

        with patch.object(
            pa_module.subprocess,
            "run",
            side_effect=OSError("permission denied"),
        ):
            result, _output, error, exc = self.call_run_codex(pa_module)

        self.assert_no_backend_exception(exc)
        self.assertEqual(result, 1)
        self.assert_concise_stderr(error)
        self.assertIn("codex", error.lower())
        self.assertIn("permission denied", error.lower())

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
            pa_module = load_pa_module()
            with redirect_stdout(output), redirect_stderr(error):
                result = pa_module.run_ollama("prompt")

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
