# Changelog

All notable user-facing changes to `pa` are documented here.

This file combines committed git history with the current working tree and prior
conversation notes. The dated sections below describe
committed git history. Planning-only notes, including the earlier Logseq
retrieval design, are intentionally excluded from the change list unless they
became implemented behavior.

## Tests
- Tests for the package split, short flags, Logseq capture, Codex session
  discovery, Ollama follow-ups, morning agent command construction, journal
  upserts, and morning workflow behavior.

## [2026-07-09]

### Changed
- Changed morning rundown weather behavior so the weather lookup is unavailable
  when no location is configured.
- Changed morning rundown weather behavior to fetch Open-Meteo directly instead
  of using a Codex web-search source agent.
- Changed morning rundown weather configuration so a local
  `$HOME/.config/personal-assistant/weather-location` file can provide the
  location without `.bashrc` or crontab edits.
- Changed morning rundown weather output to write only compact `Whole Day` and
  `Light` child lines instead of current/hourly day-part details.
- Changed morning rundown task selection to cap daily TODO output at five
  blocks while preserving short `source::`, `why::`, and `next::` details.
- Changed morning rundown source failures to produce a degraded nonzero result
  while still writing the journal block when the reviewer succeeds.
- Changed morning rundown integer environment parsing so invalid values fall
  back to defaults instead of breaking unrelated commands such as `pa --help`.

## [2026-07-04] - Hardening & Help Options

### Changed
- Changed the help contract to:
  - `pa [-c|-o] [-l] "prompt here"`
  - `pa morning-rundown [--dry-run] [--force]`
- Changed context construction so Codex receives one expanded prompt while
  Ollama receives local context as the initial system message.
- Changed context construction so `profile.md`, `memory.md`, and cwd
  `AGENTS.md` are labeled with source path, character count, presence, and
  truncation state before backend calls.
- Changed normal prompt routing so only leading flags are parsed as options;
  flags after the first prompt word are treated as prompt text.
- Changed Logseq writes to be nonfatal. Missing graph roots disable capture
  with a warning instead of blocking the selected backend.

## [2026-06-28] - Morning Rundown

### Added
- Added `pa morning-rundown [--dry-run] [--force]` for a daily planning brief
  written to the current Logseq journal.
- Added morning rundown source agents for Logseq pages, repository state, and
  news, optional Open-Meteo weather, and a reviewer agent that produces focused
  TODO items.
- Added marker-based Logseq journal upsert behavior for morning rundowns using
  `<!-- pa-morning-rundown:start YYYY-MM-DD -->` and matching end markers.
- Added morning rundown configuration through `PA_LOGSEQ_GRAPH_DIR`,
  `PA_RUNDOWN_REPOS`, `PA_RUNDOWN_WEATHER_LOCATION`,
  `PA_RUNDOWN_TASK_LIMIT`, `PA_RUNDOWN_AGENT_TIMEOUT_SECONDS`, and
  `PA_RUNDOWN_WEATHER_TIMEOUT_SECONDS`.
- Added `pa --context-preview "prompt"` to show the labeled context and backend
  message shapes without contacting Codex or Ollama.
- Added configurable context caps through `PA_CONTEXT_SECTION_CHAR_CAP`,
  `PA_PROFILE_CHAR_CAP`, `PA_MEMORY_CHAR_CAP`, and `PA_AGENTS_CHAR_CAP`.

## [2026-06-27] - Split Program Logic

### Added
- Split the CLI implementation into a thin executable `pa` launcher and the
  reusable `personal_assistant/` package.
- Added package modules for CLI parsing, routing, context construction,
  configuration, Codex backend handling, Ollama backend handling, Logseq
  capture, Codex session lookup, and morning rundown orchestration.
- Added short leading route flags:
  - `-c` forces Codex.
  - `-o` forces Ollama.
  - `-l` enables opt-in Logseq capture.
- Added Logseq capture for prompts, Ollama follow-ups, Ollama outputs, and
  backend status entries.
- Added metadata-only Codex capture with exit status, launching username,
  best-effort Codex session id, and a `codex resume SESSIONID` command when
  the session id can be found.
- Added interactive Ollama follow-up support with in-process conversation
  history until the user types exactly `exit`.

### Removed

- Removed support for the old long route flags `--codex` and `--ollama` in the
  current parser. Use `-c` and `-o` instead.

## [2026-06-25] - Flatten CLI Path

### Changed

- Moved the executable from `personal-assistant/bin/pa` to
  `personal-assistant/pa`.
- Updated tests, project docs, and agent instructions to use `pa` or `./pa`
  instead of `bin/pa`.
- Kept the CLI directly executable from the repository root.

## [2026-06-25] - Harden CLI

### Added

- Added explicit forced routing flags `--codex` and `--ollama` for the
  then-current CLI.
- Added `docs/README.md` and expanded user-facing CLI documentation.
- Added stdlib `unittest` coverage for routing and backend behavior.

### Changed

- Changed Codex execution to return the subprocess exit code to callers.
- Changed the Ollama backend to lazy-import `requests` so help and Codex routes
  can run without the dependency being installed.
- Moved usage notes into `docs/usage-analysis.md`.

### Fixed

- Reported missing `codex` and Codex start failures with concise errors.
- Added stricter validation for malformed Ollama stream chunks.
- Added clearer handling for Ollama request failures, invalid JSON, and streams
  that end before completion.

## [2026-06-23] - Initial CLI

### Added

- Added the initial `pa` command-line assistant at `personal-assistant/bin/pa`.
- Added keyword routing to send coding-like prompts to Codex and general
  prompts to Ollama.
- Added local context loading from `profile.md`, `memory.md`, and the current
  directory's `AGENTS.md`.
- Added streamed Ollama output for lower perceived latency.
- Added concise route indicators before slower backend work starts.
- Added `-h` and `--help` usage output.
- Added initial project documentation and empty `profile.md` / `memory.md`
  context files.
