# Personal Assistant

This project provides Sam's local command-line personal assistant. The user-facing command is:

```sh
pa "prompt here"
```

`pa` is configured as a shell alias in `.bashrc` and points to:

```sh
$HOME/homelab/personal-assistant/bin/pa
```

## Repository Layout

- `bin/pa`: executable Python entry point and all current application logic.
- `profile.md`: optional personal profile context loaded into each assistant prompt.
- `memory.md`: optional longer-term memory context loaded into each assistant prompt.
- `pa_usage_analysis.txt`: notes on CLI behavior and improvement ideas.
- `docs/`: project-local documentation.
- `AGENTS.md`: agent instructions for working in this repository.

The wider homelab repository also has shared agent notes under `../docs/agents/`.

## How It Works

`bin/pa` joins command-line arguments into a single prompt, reads local context from `profile.md`, `memory.md`, and the current directory's `AGENTS.md`, then routes the prompt to either Codex or Ollama.

Routing is keyword based:

- Coding-like prompts, such as prompts containing `code`, `bug`, `repo`, `git`, `test`, or `readme`, are sent to Codex.
- Other prompts are sent to Ollama at `http://localhost:11434/api/chat`.

The main Python flow is:

- `main()`: parses arguments, handles help, builds context, and returns the selected backend's exit code.
- `build_context()`: combines profile, memory, project instructions, and the user prompt.
- `should_use_codex()`: checks the prompt for coding-related keywords.
- `run_codex()`: prints a wait indicator and runs the Codex subprocess.
- `run_ollama()`: prints a wait indicator, streams Ollama output, and reports request or JSON errors.

## Usage

Show help:

```sh
pa --help
```

Ask the local Ollama-backed assistant:

```sh
pa "summarise what I should do today"
```

Ask a coding-related question, routed to Codex:

```sh
pa "review this repository"
```

## Runtime Requirements

- Python 3
- The third-party Python package `requests`
- Ollama running locally for non-coding prompts
- Codex CLI available on `PATH` for coding-related prompts
- A shell alias similar to:

```sh
alias pa="$HOME/homelab/personal-assistant/bin/pa"
```

## Validation

Run a syntax check:

```sh
python3 -m py_compile bin/pa
```

Check CLI help:

```sh
pa --help
```

Manual routing checks:

```sh
pa "hello"
pa "review this repository"
```

Expected behavior:

- `pa --help` prints usage and exits without contacting Ollama or Codex.
- Ollama-routed prompts immediately print a wait indicator, then stream the response.
- Codex-routed prompts immediately print a wait indicator, then hand off to Codex.
- Ollama connection, timeout, HTTP, or malformed JSON failures produce concise errors.

## Troubleshooting

If `pa` is not found, confirm the shell alias exists and reload the shell:

```sh
alias pa="$HOME/homelab/personal-assistant/bin/pa"
```

If Ollama prompts fail, confirm Ollama is running locally and listening on `http://localhost:11434`.

If Codex prompts fail, confirm `codex` is installed and available on `PATH`.
