# Personal Assistant

This project provides Sam's local command-line personal assistant. The user-facing command is:

```sh
pa "prompt here"
```

`pa` is configured as a shell alias in `.bashrc` and points to:

```sh
$HOME/homelab/personal-assistant/pa
```

## Repository Layout

- `pa`: executable Python entry point and all current application logic.
- `profile.md`: optional personal profile context loaded into each assistant prompt.
- `memory.md`: optional longer-term memory context loaded into each assistant prompt.
- `docs/`: project-local documentation, including usage and routing notes.
- `tests/`: automated `unittest` coverage for CLI routing behavior.
- `AGENTS.md`: agent instructions for working in this repository.

The wider homelab repository also has shared agent notes under `../docs/agents/`.

## How It Works

`pa` joins command-line arguments into a single prompt, reads local context from `profile.md`, `memory.md`, and the current directory's `AGENTS.md`, then routes the prompt to either Codex or Ollama.

Routing is keyword based unless the user forces a backend:

- Coding-like prompts, such as prompts containing `code`, `bug`, `repo`, `git`, `test`, or `readme`, are sent to Codex.
- Other prompts are sent to Ollama at `http://localhost:11434/api/chat`.
- `--codex` forces a prompt to Codex.
- `--ollama` forces a prompt to Ollama.

The main Python flow is:

- `main()`: parses arguments, handles help, builds context, and returns the selected backend's exit code.
- `build_context()`: combines profile, memory, project instructions, and the user prompt.
- `should_use_codex()`: checks the prompt for coding-related keywords.
- `run_codex()`: prints a wait indicator and runs the Codex subprocess.
- `run_ollama()`: prints a wait indicator, streams Ollama output, and reports request or JSON errors.

## Routing Reference

Prompts are routed to Codex when the user prompt contains any of these
case-insensitive keyword fragments:

```text
code
script
bug
error
traceback
repo
git
diff
patch
function
class
test
refactor
shell
bash
filesystem
file
directory
readme
agents.md
dockerfile
ansible
sshfs
logseq plugin
```

Examples that route to Codex:

```sh
pa "review this repository"
pa "fix this bash script"
pa "why does this test fail?"
```

Examples that route to Ollama:

```sh
pa "summarise what I should do today"
pa "draft a polite reply"
pa "make a packing list"
```

Keyword routing only checks the original user prompt. The added profile,
memory, and project context do not affect route selection.

Use a forced routing flag as the first argument when keyword routing would make
the wrong choice:

```sh
pa --codex "write a plan for my day in this repo"
pa --ollama "explain git in plain language"
```

Forced routing flags require a prompt. `pa --codex` and `pa --ollama` without a
prompt print usage and exit with status code 1.

## Configuration

The current CLI uses hard-coded defaults in `pa`:

- Assistant directory: `$HOME/homelab/personal-assistant`
- Profile context file: `$HOME/homelab/personal-assistant/profile.md`
- Memory context file: `$HOME/homelab/personal-assistant/memory.md`
- Project instructions file: `AGENTS.md` in the current working directory
- Ollama endpoint: `http://localhost:11434/api/chat`
- Ollama model: `llama3.1:8b`
- Ollama timeout: 120 seconds
- Codex command: `codex`

These values are not configurable through command-line flags or environment
variables yet. Update this section when configurability is added.

## Context And Privacy

Every normal prompt is expanded before it is sent to either backend. The
expanded prompt includes:

- The contents of `profile.md`, if present.
- The contents of `memory.md`, if present.
- The contents of `AGENTS.md` from the current working directory, if present.
- The user's original prompt.

Do not store secrets, credentials, private tokens, or sensitive machine-specific
details in `profile.md`, `memory.md`, or repository `AGENTS.md` files unless
you are comfortable sending that content to the selected backend.

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

Force a backend:

```sh
pa --codex "review this note even though it has no code keywords"
pa --ollama "explain this git command without opening Codex"
```

## Runtime Requirements

- Python 3
- The third-party Python package `requests`, required only for real Ollama-backed prompts
- Ollama running locally for non-coding prompts
- Codex CLI available on `PATH` for coding-related prompts
- A shell alias similar to:

```sh
alias pa="$HOME/homelab/personal-assistant/pa"
```

## Validation

Run a syntax check:

```sh
python3 -m py_compile pa
```

Run automated CLI routing and backend behavior tests:

```sh
python3 -m unittest discover -s tests
```

Check CLI help:

```sh
pa --help
```

Manual routing checks:

```sh
pa "hello"
pa "review this repository"
pa --codex "hello"
pa --ollama "review this repository"
```

Expected behavior:

- `pa --help` prints usage and exits without contacting Ollama or Codex, and should not require `requests`.
- The unittest suite verifies keyword routing, forced routing, and backend behavior with fake backends. It does not contact Ollama or Codex, and fake-backend tests should not require `requests`.
- Ollama-routed prompts immediately print a wait indicator, then stream the response.
- Codex-routed prompts immediately print a wait indicator, then hand off to Codex.
- Forced routing flags override keyword routing when they are the first argument.
- Ollama connection, timeout, HTTP, or malformed JSON failures produce concise errors.

## Troubleshooting

If `pa` is not found, confirm the shell alias exists and reload the shell:

```sh
alias pa="$HOME/homelab/personal-assistant/pa"
```

If Ollama prompts fail, confirm Ollama is running locally and listening on `http://localhost:11434`.

If real Ollama prompts print `Ollama backend requires the Python package 'requests'.`, install `requests` for the Python environment running `pa`.

If Codex prompts fail, confirm `codex` is installed and available on `PATH`.

If Codex prompts print `Codex command not found: codex`, install the Codex CLI or update `PATH` so `pa` can find it.

If Ollama prompts print `Ollama returned malformed stream: expected JSON object with optional message object.`, check the local Ollama service or any proxy returning the stream.
