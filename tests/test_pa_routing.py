import io
import sys
import unittest
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
PA_PATH = REPO_ROOT / "pa"


def load_pa_module():
    loader = SourceFileLoader("pa_under_test", str(PA_PATH))
    spec = spec_from_loader(loader.name, loader)
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


@contextmanager
def requests_import_unavailable():
    real_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "requests" or name.startswith("requests."):
            raise ModuleNotFoundError("No module named 'requests'")
        return real_import(name, globals, locals, fromlist, level)

    with patch("builtins.__import__", side_effect=fake_import):
        yield


def install_fake_backends(pa_module):
    calls = []

    def fake_codex(prompt):
        calls.append(("codex", prompt))
        return 0

    def fake_ollama(prompt):
        calls.append(("ollama", prompt))
        return 0

    pa_module.run_codex = fake_codex
    pa_module.run_ollama = fake_ollama
    return calls


class RoutingTests(unittest.TestCase):
    def run_pa(self, argv):
        pa_module = load_pa_module()
        calls = install_fake_backends(pa_module)
        pa_module.build_context = lambda prompt: f"CTX::{prompt}"

        with patch.object(sys, "argv", argv):
            result = pa_module.main()

        return result, calls

    def test_codex_flag_forces_codex_for_non_coding_prompt(self):
        result, calls = self.run_pa(["pa", "--codex", "hello"])

        self.assertEqual(result, 0)
        self.assertEqual(calls, [("codex", "CTX::hello")])

    def test_ollama_flag_forces_ollama_for_coding_prompt(self):
        result, calls = self.run_pa(
            ["pa", "--ollama", "review", "this", "repository"]
        )

        self.assertEqual(result, 0)
        self.assertEqual(calls, [("ollama", "CTX::review this repository")])

    def test_default_keyword_routing_still_uses_codex_for_coding_prompt(self):
        result, calls = self.run_pa(["pa", "review", "this", "repository"])

        self.assertEqual(result, 0)
        self.assertEqual(calls, [("codex", "CTX::review this repository")])

    def test_default_keyword_routing_still_uses_ollama_for_general_prompt(self):
        result, calls = self.run_pa(["pa", "hello"])

        self.assertEqual(result, 0)
        self.assertEqual(calls, [("ollama", "CTX::hello")])

    def test_forced_route_without_prompt_prints_usage_and_fails(self):
        for flag in ("--codex", "--ollama"):
            pa_module = load_pa_module()
            calls = install_fake_backends(pa_module)
            output = io.StringIO()

            with self.subTest(flag=flag):
                with patch.object(sys, "argv", ["pa", flag]):
                    with redirect_stdout(output):
                        result = pa_module.main()

                self.assertEqual(result, 1)
                self.assertEqual(calls, [])
                self.assertIn("Usage:", output.getvalue())

    def test_module_loads_and_help_runs_without_requests_dependency(self):
        output = io.StringIO()

        with requests_import_unavailable():
            try:
                pa_module = load_pa_module()
            except ModuleNotFoundError as exc:
                self.fail(f"pa should load without requests installed: {exc}")

            with patch.object(sys, "argv", ["pa", "--help"]):
                with redirect_stdout(output):
                    result = pa_module.main()

        self.assertEqual(result, 0)
        self.assertIn("Usage:", output.getvalue())

    def test_codex_routed_fake_backend_works_without_requests_dependency(self):
        with requests_import_unavailable():
            try:
                pa_module = load_pa_module()
            except ModuleNotFoundError as exc:
                self.fail(f"Codex routing should not require requests: {exc}")

            calls = install_fake_backends(pa_module)
            pa_module.build_context = lambda prompt: f"CTX::{prompt}"

            with patch.object(sys, "argv", ["pa", "review", "this", "repository"]):
                result = pa_module.main()

        self.assertEqual(result, 0)
        self.assertEqual(calls, [("codex", "CTX::review this repository")])

    def test_run_ollama_reports_missing_requests_dependency(self):
        error = io.StringIO()

        with requests_import_unavailable():
            try:
                pa_module = load_pa_module()
            except ModuleNotFoundError as exc:
                self.fail(f"pa should load before reporting dependency errors: {exc}")

            with redirect_stderr(error):
                try:
                    result = pa_module.run_ollama("prompt")
                except ModuleNotFoundError as exc:
                    self.fail(f"run_ollama should report missing requests cleanly: {exc}")

        self.assertEqual(result, 1)
        self.assertEqual(
            error.getvalue().strip(),
            "Ollama backend requires the Python package 'requests'.",
        )


if __name__ == "__main__":
    unittest.main()
