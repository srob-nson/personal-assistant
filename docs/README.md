# Personal Assistant Docs

This directory holds project-local documentation for the personal assistant CLI.

## Contents

- `personal-assistant.md`: user-facing overview, usage, routing behavior, configuration defaults, validation, and troubleshooting.
- `usage-analysis.md`: historical notes on CLI behavior and already-implemented usability improvements.

## Related Files

- `../pa`: executable Python entry point and all current application logic.
- `../profile.md`: optional profile context included in assistant prompts.
- `../memory.md`: optional memory context included in assistant prompts.
- `../AGENTS.md`: repository instructions for coding agents working on this project.

When behavior changes in `pa`, update `personal-assistant.md` in the same change so usage, routing, configuration, and validation notes stay accurate.
