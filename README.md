# Personal Assistant

Small Python CLI for local assistant workflows. It routes coding-style prompts
to Codex, routes general prompts to a local Ollama backend, can capture prompt
metadata in Logseq, and can generate a daily morning rundown.

## Usage

```sh
./pa --help
./pa "summarise what I should do today"
./pa "review this repository"
./pa morning-rundown --dry-run
```

Use `-c` to force Codex, `-o` to force Ollama, and `-l` to capture prompt and
backend output/status metadata in Logseq.

## Development

Run the basic checks before committing code changes:

```sh
python3 -m py_compile pa personal_assistant/*.py personal_assistant/backends/*.py
python3 -m unittest discover -s tests
./pa --help
```

The CLI needs Python 3. Real Ollama-backed prompts require the third-party
`requests` package and a local Ollama service. Coding prompts and morning
rundown agents require the Codex CLI.

## Local Files

`AGENTS.md`, `Loop.md`, `memory.md`, `next.md`, and `profile.md` are local
assistant context or working-note files. They are intentionally ignored so they
can stay on this machine without being tracked in GitHub.

See `docs/personal-assistant.md` for the full usage and configuration guide.
