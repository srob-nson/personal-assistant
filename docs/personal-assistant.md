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

- `pa`: executable Python entry point that delegates to `personal_assistant.cli`.
- `personal_assistant/`: application package containing CLI orchestration, context, routing, configuration, and backend adapters.
- `profile.md`: optional personal profile context loaded into assistant requests.
- `memory.md`: optional longer-term memory context loaded into assistant requests.
- `docs/`: project-local documentation, including usage and routing notes.
- `tests/`: automated `unittest` coverage for CLI routing behavior.
- `AGENTS.md`: agent instructions for working in this repository.

The wider homelab repository also has shared agent notes under `../docs/agents/`.

## How It Works

`pa` is a thin launcher. The package CLI joins command-line arguments into a single prompt, reads local context from `profile.md`, `memory.md`, and the current directory's `AGENTS.md`, then routes the prompt to either Codex or Ollama. When `-l` is provided, it also writes prompt/output metadata to Logseq pages.

The CLI also has a non-interactive morning rundown command:

```sh
pa morning-rundown
```

That command dispatches read-only Codex background agents for Logseq, repository, news, weather, and final review work, then writes the final focused task list into that day's Logseq journal.

Routing is keyword based unless the user forces a backend:

- Coding-like prompts, such as prompts containing `code`, `bug`, `repo`, `git`, `test`, or `readme`, are sent to Codex.
- Other prompts start an Ollama-backed conversation at `http://localhost:11434/api/chat`.
- `-c` forces a prompt to Codex.
- `-o` forces a prompt to Ollama.
- `-l` captures the interaction in Logseq.

The main Python flow is split by responsibility:

- `personal_assistant.cli.main()`: parses arguments, handles help, routes on the original user prompt, optionally records the initial prompt, and returns the selected backend's exit code.
- `personal_assistant.context`: combines profile, memory, project instructions, and user prompt data for each backend.
- `personal_assistant.logseq`: appends opt-in prompt, output, and status entries to Logseq pages.
- `personal_assistant.codex_sessions`: finds a best-effort Codex session id for later `codex resume SESSIONID`.
- `personal_assistant.routing`: checks prompts for coding-related keywords.
- `personal_assistant.backends.codex`: prints a wait indicator and runs the Codex subprocess.
- `personal_assistant.backends.ollama`: prints a wait indicator, streams Ollama output, keeps in-session conversation history, and reports request or JSON errors.
- `personal_assistant.morning`: orchestrates the morning rundown workflow.
- `personal_assistant.morning_agents`: runs source and reviewer agents through `codex exec`.
- `personal_assistant.morning_journal`: writes and replaces generated Logseq journal blocks.

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

Keyword routing only checks the original user prompt. Added profile, memory,
project context, and later Ollama follow-up messages do not affect route
selection.

Use a forced routing flag as the first argument when keyword routing would make
the wrong choice:

```sh
pa -c "write a plan for my day in this repo"
pa -o "explain git in plain language"
```

Forced routing flags require a prompt. `pa -c`, `pa -o`, and `pa -l` without a
prompt print usage and exit with status code 1. `-c`, `-o`, and `-l` are leading
flags; flags after the first prompt word are treated as prompt text.

## Ollama Conversations

Ollama-routed prompts are interactive. After each completed Ollama response,
`pa` prompts for another message:

```text
Follow-up (type exit to quit):
```

Each follow-up sends the full in-process message history back to Ollama, so the
local model can use previous user messages and assistant responses during the
current session. Type exactly `exit` to end the session with status code 0.
Other spellings, capitalization, or surrounding spaces are treated as normal
follow-up messages. Blank or whitespace-only follow-ups are ignored and prompt
again without contacting Ollama.

At the follow-up prompt, EOF exits cleanly with status code 0. Ctrl-C during
Ollama streaming or follow-up input prints `Interrupted.` and returns status
code 130.

The profile, memory, and current directory `AGENTS.md` context are loaded once
at the start of the Ollama session as the system message. Follow-up turns are
not written to `memory.md`, and context files are not refreshed until the next
`pa` command.

When `-l` is enabled, accepted follow-up prompts are appended to Logseq
`Prompts.md`, and completed Ollama assistant responses are appended to
`Outputs.md`. Partial streamed output from failed Ollama responses is not
recorded.

## Logseq Capture

Use `-l` to append a basic record of the interaction to Logseq:

```sh
pa -l "save this prompt and Ollama output"
pa -l -c "save this Codex prompt and status"
pa -l -o "force Ollama and save prompt/output"
```

Logseq capture writes to:

- `pages/Prompts.md`: initial prompts and Ollama follow-up prompts.
- `pages/Outputs.md`: Ollama responses and backend status entries.

Every entry includes a `pa` session id, turn number, route, kind, timestamp, and
launching username so Prompts and Outputs entries can be matched later. Codex
capture does not store the full Codex transcript. It stores status metadata,
including the Codex exit code and, when discoverable, a Codex session id plus a
`codex resume SESSIONID` command.

## Morning Rundown

Use `pa morning-rundown` to generate a daily planning brief:

```sh
pa morning-rundown
pa morning-rundown --dry-run
pa morning-rundown --force
```

The command reads the Logseq graph from `PA_LOGSEQ_GRAPH_DIR`, defaulting to
`$HOME/homelab/logseq2-0`. It expects these pages when available:

- `pages/Goals.md`
- `pages/Tasks.md`
- `pages/Projects.md`

It writes to the local-date journal path:

```text
journals/YYYY_MM_DD.md
```

Generated journal content is wrapped in date-specific markers:

```text
<!-- pa-morning-rundown:start YYYY-MM-DD -->
...
<!-- pa-morning-rundown:end YYYY-MM-DD -->
```

If today's generated block already exists, the command exits without changing
the journal. Use `--force` to replace today's generated block. Use `--dry-run`
to print the generated block without writing the journal.

The workflow runs source agents first, then a reviewer agent:

- `logseq`: reads Goals, Tasks, and Projects pages.
- `repo`: inspects configured repositories with read-only Git commands.
- `news`: uses Codex web search for current world news.
- `weather`: uses Codex web search for the location in `PA_RUNDOWN_WEATHER_LOCATION`.
- `reviewer`: turns source summaries into focused Logseq TODO items.

Codex agents run through `codex exec` with read-only sandboxing and approval
disabled for unattended cron use. The news and weather agents are the only
agents launched with web search enabled. The journal stores the final rundown
and source statuses, not full raw agent transcripts.

Cron is not installed automatically. Create the log directory first:

```sh
mkdir -p /home/jellyfish/.local/state/personal-assistant
```

Then add a user crontab entry with an explicit environment:

```cron
CRON_TZ=Europe/London
HOME=/home/jellyfish
PATH=/home/jellyfish/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
PA_LOGSEQ_GRAPH_DIR=/home/jellyfish/homelab/logseq2-0
PA_RUNDOWN_REPOS=/home/jellyfish/homelab
# Optional, enables weather:
# PA_RUNDOWN_WEATHER_LOCATION=<LOCAL_AREA>

0 6 * * * cd /home/jellyfish/homelab/personal-assistant && ./pa morning-rundown >> /home/jellyfish/.local/state/personal-assistant/morning-rundown.cron.log 2>&1
```

Rollback is removing that crontab line and any `PA_*` variables added only for
this job.

## Configuration

The current CLI uses hard-coded defaults in `personal_assistant.config`:

- Assistant directory: `$HOME/homelab/personal-assistant`
- Profile context file: `$HOME/homelab/personal-assistant/profile.md`
- Memory context file: `$HOME/homelab/personal-assistant/memory.md`
- Project instructions file: `AGENTS.md` in the current working directory
- Ollama endpoint: `http://localhost:11434/api/chat`
- Ollama model: `llama3.1:8b`
- Ollama timeout: 120 seconds
- Codex command: resolved from `PA_CODEX_COMMAND`, then `PATH`, then `$HOME/.local/bin/codex`, then `codex`
- Logseq graph: `$HOME/homelab/logseq2-0`, overridden by `PA_LOGSEQ_GRAPH_DIR`
- Codex sessions directory: `$HOME/.codex/sessions`, overridden by `PA_CODEX_SESSIONS_DIR`
- Morning rundown repositories: `$HOME/homelab`, overridden by `PA_RUNDOWN_REPOS`
- Morning rundown weather location: unset by default, set with `PA_RUNDOWN_WEATHER_LOCATION`
- Morning rundown task limit: `7`, overridden by `PA_RUNDOWN_TASK_LIMIT`
- Morning rundown agent timeout: `300` seconds, overridden by `PA_RUNDOWN_AGENT_TIMEOUT_SECONDS`

Backend and context paths remain hard-coded defaults. Logseq and Codex session
paths can be overridden with environment variables for testing or alternate
local layouts.

## Context And Privacy

Every backend request includes local context, but Codex and Ollama receive that
context in different shapes.

Codex receives one expanded prompt containing:

- The contents of `profile.md`, if present.
- The contents of `memory.md`, if present.
- The contents of `AGENTS.md` from the current working directory, if present.
- The user's original prompt.

Ollama receives the profile, memory, and current directory `AGENTS.md` content
as the first system message, then keeps the user's original prompt, assistant
responses, and follow-up prompts as separate chat messages for that process.

Do not store secrets, credentials, private tokens, or sensitive machine-specific
details in `profile.md`, `memory.md`, or repository `AGENTS.md` files unless
you are comfortable sending that content to the selected backend.

Logseq capture is opt-in per command. Prompt entries store the raw post-flag
user prompt, not the expanded Codex prompt and not Ollama's system message.
Output entries can still contain sensitive information if the assistant repeats,
summarizes, or infers it from prompt or context.

Morning rundown agents may read the configured Logseq pages and repository
state directly. They run read-only, but their prompts and summaries are handled
by Codex. Keep secrets out of Goals, Tasks, Projects, repo status, and nearby
project files if you do not want them visible to those agents.

## Usage

Show help:

```sh
pa --help
```

Ask the local Ollama-backed assistant:

```sh
pa "summarise what I should do today"
```

Continue the conversation at the follow-up prompt, or type `exit` to end it.

Ask a coding-related question, routed to Codex:

```sh
pa "review this repository"
```

Force a backend:

```sh
pa -c "review this note even though it has no code keywords"
pa -o "explain this git command without opening Codex"
```

Capture a prompt and backend output/status in Logseq:

```sh
pa -l "summarise what I should do today"
pa -l -c "review this repository"
```

Generate the morning rundown:

```sh
PA_RUNDOWN_WEATHER_LOCATION="<LOCAL_AREA>" pa morning-rundown --dry-run
PA_RUNDOWN_WEATHER_LOCATION="<LOCAL_AREA>" pa morning-rundown
```

## Runtime Requirements

- Python 3
- The third-party Python package `requests`, required only for real Ollama-backed prompts
- Ollama running locally for non-coding prompts
- Codex CLI available on `PATH` for coding-related prompts and morning rundown agents
- Codex web search available for morning rundown news and weather agents
- A shell alias similar to:

```sh
alias pa="$HOME/homelab/personal-assistant/pa"
```

## Validation

Run a syntax check:

```sh
python3 -m py_compile pa personal_assistant/*.py personal_assistant/backends/*.py
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
pa -c "hello"
pa -o "review this repository"
PA_RUNDOWN_WEATHER_LOCATION="<LOCAL_AREA>" pa morning-rundown --dry-run
```

Expected behavior:

- `pa --help` prints usage and exits without contacting Ollama or Codex, and should not require `requests`.
- The unittest suite verifies keyword routing, forced routing, Ollama conversation behavior, and backend behavior with fake backends. It does not contact Ollama or Codex, and fake-backend tests should not require `requests`.
- Ollama-routed prompts immediately print a wait indicator, stream the response, and then prompt for follow-up input until exact `exit`.
- Codex-routed prompts immediately print a wait indicator, then hand off to Codex.
- Forced routing flags override keyword routing when they are the first argument.
- `-l` appends prompt/output/status entries to Logseq when the graph path is available, and warns without blocking backend execution when Logseq capture fails.
- `pa morning-rundown --dry-run` prints the generated journal block without writing a journal file.
- `pa morning-rundown` writes a generated block into today's Logseq journal and skips if today's block already exists.
- Ollama connection, timeout, HTTP, malformed JSON, or interrupted-session failures produce concise errors or exit statuses.

## Troubleshooting

If `pa` is not found, confirm the shell alias exists and reload the shell:

```sh
alias pa="$HOME/homelab/personal-assistant/pa"
```

If Ollama prompts fail, confirm Ollama is running locally and listening on `http://localhost:11434`.

If real Ollama prompts print `Ollama backend requires the Python package 'requests'.`, install `requests` for the Python environment running `pa`.

If Codex prompts fail, confirm `codex` is installed and available on `PATH`, or set `PA_CODEX_COMMAND` to the executable path.

If Codex prompts print `Codex command not found: codex`, install the Codex CLI, update `PATH`, or set `PA_CODEX_COMMAND`.

If Ollama prompts print `Ollama returned malformed stream: expected JSON object with optional message object.`, check the local Ollama service or any proxy returning the stream.

If `pa -l` prints `Logseq capture disabled`, confirm `PA_LOGSEQ_GRAPH_DIR` points at an existing Logseq graph directory.

If `pa morning-rundown` prints that the Logseq graph is missing, confirm `PA_LOGSEQ_GRAPH_DIR` points at the graph root, not the `pages/` directory.

If the weather source says the location is unavailable, set `PA_RUNDOWN_WEATHER_LOCATION` in the shell or crontab entry.

If the cron job does not run, confirm the crontab line uses absolute paths, includes `CRON_TZ=Europe/London` if local-time scheduling matters, and writes logs to an existing directory.
