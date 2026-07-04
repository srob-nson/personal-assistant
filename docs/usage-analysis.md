# Usage Analysis

The CLI uses a thin Python entry point and package implementation. When it is
run without arguments, `personal_assistant.cli.main()` prints:

```text
Usage: pa [-c|-o] [-l] "prompt here"
```

and exits with status code 1. For normal prompts, it joins all command-line
arguments into one prompt, routes the request either to Codex or Ollama based on
simple keyword matching unless `-c` or `-o` is provided as a leading flag, and
adds local context from profile, memory, and `AGENTS.md` for the selected
backend. With `-l`, it also appends raw prompts, Ollama outputs, and backend
status entries to Logseq `Prompts.md` and `Outputs.md` pages.

## Implemented Improvements

1. Add a `--help` / `-h` path.
   Supporting `pa --help` and `pa -h` makes the CLI easier to discover
   without changing normal behavior.

2. Return Codex's exit code from `main()`.
   Exiting with the Codex subprocess code makes failures visible to shell
   scripts and callers.

3. Add a timeout to the Ollama request.
   A timeout plus a concise error message makes failures easier to understand.

4. Stream Ollama responses.
   Streaming output lowers perceived latency because the user sees tokens as
   Ollama generates them instead of waiting for the full response.

5. Print route indicators.
   Both Ollama and Codex paths now print a short message before the slower
   backend work begins.

6. Add forced routing flags.
   Supporting `pa -c "prompt"` and `pa -o "prompt"` lets the user bypass
   keyword routing when the automatic route would make the wrong choice.

7. Keep Ollama conversations in process.
   Ollama-routed prompts now keep a local message history and prompt for
   follow-up input until the user types exactly `exit`. This gives local models
   prior user and assistant turns during the current session without writing
   follow-ups to `memory.md`.

8. Add opt-in Logseq capture.
   Supporting `pa -l "prompt"` appends prompts to `Prompts.md`, Ollama outputs
   to `Outputs.md`, and Codex status/resume metadata to `Outputs.md` without
   capturing the full Codex transcript.
