# Repository Guidelines

## Project Structure & Module Organization

This repository currently contains a small Python command-line assistant:

- `pa`: executable Python entry point and all application logic.
- `docs/`: user-facing or design documentation.
- `tests/`: stdlib `unittest` coverage for CLI behavior that should not contact local services.
- `profile.md`: optional profile context loaded into assistant prompts.
- `memory.md`: optional memory context loaded into assistant prompts.

There is no separate `src/` or asset tree yet. If the CLI grows, prefer moving reusable logic into a package directory such as `personal_assistant/` and keeping `pa` as a thin launcher.

## Build, Test, and Development Commands

- `pa "prompt here"`: run the local assistant through the user's shell alias, which points to `$HOME/homelab/personal-assistant/pa`.
- `./pa "prompt here"`: run the executable directly from the repository when the shell alias is unavailable.
- `pa "review this repository"`: delegate a coding-style prompt to Codex through keyword routing.
- `python3 -m py_compile pa`: perform a basic syntax check.
- `python3 -m unittest discover -s tests`: run the automated CLI routing and backend behavior tests with fake backends, without contacting Ollama or Codex.

The script depends on Python 3 and the third-party `requests` package. No lockfile or requirements file is present, so document any new dependencies when adding them.

## Coding Style & Naming Conventions

Use straightforward Python 3 style with 4-space indentation. Keep constants in `UPPER_SNAKE_CASE`, functions in `snake_case`, and command modes as short lowercase strings. Favor small functions with explicit return types, as in `ask_ollama(prompt: str) -> str`.

Preserve the CLI’s concise output style. User-facing messages should be direct and practical, without verbose logging unless a debug mode is added.

## Testing Guidelines

Automated tests use Python's stdlib `unittest` under `tests/`. Before committing, at minimum run:

```sh
python3 -m py_compile pa
python3 -m unittest discover -s tests
./pa --help
```

For CLI behavior changes, manually exercise the affected path where local services are available:

```sh
pa "hello"
pa "review this repository"
```

Useful pre-commit checks to consider:

- `python3 -m py_compile pa`: catches Python syntax errors.
- `python3 -m unittest discover -s tests`: checks CLI routing and backend behavior with fake backends, without requiring Ollama or Codex.
- `./pa --help`: verifies argument parsing without requiring Ollama or Codex.
- `pa "hello"`: verifies the Ollama route, visible wait indicator, and streaming output.
- `pa "review this repository"`: verifies the Codex route and startup indicator.
- `git diff --stat` and `git diff`: review the exact changes before committing.

Keep tests under `tests/` and name files `test_*.py`. Use fake backend functions or mocks for network calls to Ollama and subprocess calls to Codex so tests do not require local services.

## Commit & Pull Request Guidelines

Git history is available but sparse from this checkout, so no detailed project-specific commit convention can be inferred. Use concise imperative commit subjects such as `Add Ollama timeout handling` or `Document CLI setup`.

Pull requests should describe the user-visible change, list manual or automated verification, and note any new runtime dependencies or local services required. Include terminal output snippets for CLI behavior changes when useful.

## Security & Configuration Tips

Do not commit secrets, local model credentials, or machine-specific paths. Keep external endpoints configurable if adding more services, and retain timeouts for network requests.
