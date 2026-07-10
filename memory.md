---
# Memory
---

## 2026-07-09 PA-001 planned

Status: planned. The first `Loop.md` task is context privacy controls and
preview. Planned files are `personal_assistant/context.py`,
`personal_assistant/cli.py`, `personal_assistant/config.py`,
`tests/test_pa_backends.py`, and `tests/test_pa_routing.py`. The change should
cap and label `profile.md`, `memory.md`, and cwd `AGENTS.md`, add
`pa --context-preview "prompt"`, keep preview mode backend-free, and preserve
raw prompt-only Logseq capture.

## 2026-07-09 PA-001 fixing

Status: fixing. The first reviewer rejected the initial PA-001 diff package
because it was generated against `HEAD` in a dirty repo and included
pre-existing morning-rundown config changes from the baseline. The code path
also needs stronger tests for real CLI preview output, preview plus `-l`, and
`PA_*` context cap parsing before re-review.

## 2026-07-09 PA-001 verified

Status: verified. `pa --context-preview "prompt"` now prints the capped and
labeled Codex expanded-prompt shape and the Ollama system/user message shape
without contacting either backend or starting Logseq capture. Context from
`profile.md`, `memory.md`, and cwd `AGENTS.md` includes source path, character
count, presence, and truncation state; caps are configurable with
`PA_CONTEXT_SECTION_CHAR_CAP`, `PA_PROFILE_CHAR_CAP`, `PA_MEMORY_CHAR_CAP`, and
`PA_AGENTS_CHAR_CAP`. Verification passed with py_compile, 90 unittest tests,
both help commands, `git diff --check`, and a manual capped preview check.
