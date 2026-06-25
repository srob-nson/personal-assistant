# Usage Analysis

The CLI is a compact Python entry point. When it is run without arguments,
`main()` prints:

```text
Usage: pa [--codex|--ollama] "prompt here"
```

and exits with status code 1. For normal prompts, it joins all command-line
arguments into one prompt, builds context from profile, memory, and `AGENTS.md`,
then routes the request either to Codex or Ollama based on simple keyword
matching unless `--codex` or `--ollama` is provided as the first argument.

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
   Supporting `pa --codex "prompt"` and `pa --ollama "prompt"` lets the user
   bypass keyword routing when the automatic route would make the wrong choice.
