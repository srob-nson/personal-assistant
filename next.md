# Personal Assistant Next Changes

## Task State Format

Future Orchestrator updates to active or tracked durable task records in this file must keep each record in this compact shape. Priority-list items may remain as plain backlog entries until the Orchestrator starts or updates them, at which point the item is converted into a durable task record.

```md
### PA-001: Short title

- priority: 1
- status: todo
- plan_attempts: 0
- implementation_attempts: 0
- fix_attempts: 0
- validation_result: not_run
- latest_failure_summary: none
- changelog_status: not_needed
- memory_status: not_needed
- baseline: not_recorded
- evidence: not_recorded
```

Allowed `status` values are `todo`, `planning`, `planned`, `implementing`, `reviewing`, `fixing`, `verifying`, `done`, and `blocked`.

Allowed `validation_result` values are `not_run`, `passed`, `failed`, `preflight_failed`, and `blocked`.

Use `baseline` for the base `HEAD`, scoped `personal-assistant` state, repo-wide dirty summary, and candidate materialization notes. Use `evidence` for before/after commands, verifier command results, and diff references.

## Priority Changes

1. Harden the main Codex route.
   Update `personal_assistant/backends/codex.py` so normal `pa -c` or keyword-routed Codex runs use explicit Codex CLI arguments instead of relying on `codex` defaults. Match the safer morning-agent pattern where practical: `exec`, read-only sandbox by default, no approval prompts for automated paths, controlled working directory, and a timeout.

2. Put limits around injected context.
   Add size caps and clear labels for `profile.md`, `memory.md`, and cwd `AGENTS.md` content in `personal_assistant/context.py`. Avoid silently sending unlimited personal or project context into every backend call.

3. Make routing less surprising.
   Replace broad substring matching in `personal_assistant/routing.py` with safer matching rules. At minimum, avoid tiny generic words such as `file`, `class`, and `test` triggering Codex in casual prompts, or require explicit `-c` for high-risk Codex routing.

4. Preserve morning rundown provenance.
   Update `_extract_tasks` in `personal_assistant/morning.py` so reviewer-produced `source::` and `why::` lines survive into the Logseq journal instead of keeping only the first TODO line.

5. Treat failed source agents as degraded runs.
   Change `run_morning_rundown` so failed Logseq, repo, news, or weather source agents are reflected in the exit behavior or journal output more strongly. A reviewer success should not fully hide broken inputs.

6. Enforce or narrow Logseq read scope.
   The morning Logseq source agent is told to inspect only Goals, Tasks, and Projects, but that is currently a prompt instruction rather than an access boundary. Prefer passing only extracted page text to the agent, or use a temporary directory containing only the allowed pages.

7. Reduce Codex session-id race risk.
   Tighten `personal_assistant/codex_sessions.py` so Logseq metadata is less likely to capture an unrelated concurrent Codex session. Consider narrowing by run directory, command output, or a tighter timestamp window.

8. Clean up git tracking.
   Review the current dirty worktree and make sure `personal_assistant/` and the new tests are intentionally tracked before further work depends on them.

## Suggested Validation

- `python3 -m py_compile pa personal_assistant/*.py personal_assistant/backends/*.py`
- `python3 -m unittest discover -s tests`
- `./pa --help`
- `./pa morning-rundown --help`
- `git diff --check`

## Short Prompt For A New Agent

You are working in `/home/jellyfish/homelab/personal-assistant`. Read `AGENTS.md` and `next.md` first. Implement the priority changes in `next.md` conservatively, keeping `pa` as a thin launcher and preserving the existing concise CLI style. Start with tests for each behavior change, do not contact real Ollama or Codex in automated tests, and do not revert unrelated dirty worktree changes. Validate with `python3 -m py_compile pa personal_assistant/*.py personal_assistant/backends/*.py`, `python3 -m unittest discover -s tests`, `./pa --help`, `./pa morning-rundown --help`, and `git diff --check`.
