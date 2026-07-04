# Personal Assistant Docs

This directory holds project-local documentation for the personal assistant CLI.

## Contents

- `personal-assistant.md`: user-facing overview, usage, routing behavior, morning rundown, configuration defaults, validation, and troubleshooting.
- `usage-analysis.md`: historical notes on CLI behavior and already-implemented usability improvements.

## Related Files

- `../pa`: executable Python entry point that delegates to the package CLI.
- `../personal_assistant/`: application package for CLI orchestration, context, routing, configuration, and backend adapters.
- `../personal_assistant/morning.py`: morning rundown orchestration for Logseq journal output.
- `../profile.md`: optional profile context included in assistant requests.
- `../memory.md`: optional memory context included in assistant requests.
- `../AGENTS.md`: repository instructions for coding agents working on this project.

When CLI behavior changes, update `personal-assistant.md` in the same change so usage, routing, configuration, and validation notes stay accurate.
