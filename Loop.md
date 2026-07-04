# Loop: implement-new

This is a prompt-only orchestration runbook for agent-driven implementation in `/home/jellyfish/homelab/personal-assistant`.

It is not machine-executable config. A human or supervising agent must enforce the loop rules, state transitions, stop conditions, and validation gates.

## Goal

Implement the priority changes in `next.md` conservatively while keeping `pa` as a thin launcher and preserving the existing concise CLI style.

## Required Context

Before each loop iteration, read these files fresh:

- `AGENTS.md`
- `next.md`
- `CHANGELOG.md`
- `memory.md`
- The relevant implementation files and tests for the active task

Automated tests must not contact real Ollama or real Codex. Use fake backends, mocks, or help-only CLI invocations.

Do not revert unrelated dirty worktree changes.

## Queue And State

`next.md` is the durable queue and cursor for this loop.

The Orchestrator is the only role allowed to update:

- `next.md`
- `memory.md`
- `CHANGELOG.md`

All other roles return reports only.

Use only these task statuses:

- `todo`
- `planning`
- `planned`
- `implementing`
- `reviewing`
- `fixing`
- `verifying`
- `done`
- `blocked`

Task selection rule:

1. If any task is in `planning`, `planned`, `implementing`, `reviewing`, `fixing`, or `verifying`, continue that task.
2. Otherwise, choose the first `todo` task in priority order from `next.md`.
3. Do not start a new task while another task is active.
4. Do not delete completed tasks from `next.md`.

Each task should track:

- task id
- priority
- title
- status
- plan attempts
- implementation attempts
- fix attempts
- validation result
- latest failure summary
- changelog status
- memory status

## Preflight

At the start of each task, the Orchestrator records the baseline state.

Run these commands from the Git root, `/home/jellyfish/homelab`:

```sh
git rev-parse HEAD
git status --short -- personal-assistant
git diff --stat -- personal-assistant
```

Also record untracked files under `personal-assistant`.

Dirty files are baseline input, not completed work.

If the baseline is unclear, contains secrets, includes deploy or migration changes, or has ownership conflicts, mark the task `blocked` and ask for human direction.

## Workflow

### 1. Planner

The Planner reads fresh context and produces a full task plan.

The Planner must include:

- files likely to change
- behavior changes
- tests to add or update
- commands to run
- risks and edge cases
- rollback notes if relevant

When planning starts, the Orchestrator sets the task status to `planning` and increments the plan attempt count.

When planning is accepted, the Orchestrator sets the task status to `planned`.

### 2. Memory Planning Note

The Orchestrator may add or update a short `memory.md` note with status `planned`.

The note must not claim implementation success.

### 3. Implementers

The Orchestrator starts two independent Implementer agents.

Each Implementer works in its own isolated tree.

Both Implementers must start from the same baseline:

- same base `HEAD`
- same scoped dirty tracked diff
- same scoped untracked files copied into the tree

If the baseline cannot be materialized cleanly, stop and mark the task `blocked`.

Implementers must:

- start with tests for behavior changes
- avoid contacting real Ollama or Codex in automated tests
- avoid unrelated refactors
- avoid changing shared documentation files unless the task requires it
- report changed files, test evidence, and remaining risks

The two Implementers count as one implementation attempt.

### 4. Reviewer

The Reviewer compares both implementation candidates.

The Reviewer must decide one of:

- choose Implementer A
- choose Implementer B
- synthesize both in a separate integration tree
- reject both and send the task to `fixing`

The Reviewer checks:

- correctness against the plan
- test coverage
- fake or mocked external services
- compatibility with the dirty baseline
- whether the change preserves concise CLI behavior
- whether changelog or memory updates are warranted

The Reviewer must not mark the task complete.

### 5. Integration

The Orchestrator integrates the selected candidate into the primary worktree or a dedicated integration tree.

If the selected patch overlaps with files that changed in the primary worktree after preflight, pause and report the overlapping paths.

Do not use destructive commands such as:

- `git reset --hard`
- `git checkout --`
- `git clean`

unless a human explicitly approves that action.

### 6. Verifier

The Verifier runs the full required validation suite from the integration tree.

Required commands:

```sh
python3 -m py_compile pa personal_assistant/*.py personal_assistant/backends/*.py
python3 -m unittest discover -s tests
./pa --help
./pa morning-rundown --help
git diff --check
```

The Verifier must report:

- run id
- worktree path
- branch
- base `HEAD`
- selected candidate
- exact command
- working directory
- exit code for each command
- key output for each command
- unit test count and final `OK` or failure summary
- first usage line from each help command
- `git diff --stat`
- `git diff --name-only`
- `git diff --check` result
- confirmation that automated validation did not contact real Ollama or real Codex

If any command fails or is skipped, the task is not verified.

### 7. Orchestrator Completion

The Orchestrator may mark a task `done` only after all of these are true:

- review passed
- all verifier commands exited `0`
- `CHANGELOG.md` was updated if user-visible behavior changed
- `memory.md` has a short verified task note
- `next.md` reflects the final task status

`CHANGELOG.md` records only verified user-visible changes.

`memory.md` may record planned, blocked, failed, or verified work, but must label the status clearly.

Never write `passed`, `complete`, `done`, or `implemented` unless verifier evidence includes all required commands with exit code `0`.

## Error Handling

If baseline validation fails before implementation:

1. Mark the task `blocked`.
2. Set validation to `baseline_failed`.
3. Record the failed command and short failure summary in `next.md`.
4. Add a concise `blocked` note to `memory.md`.
5. Do not advance to the next task.

If review or validation fails after implementation:

1. Keep the same active task.
2. Set status to `fixing`.
3. Increment the fix attempt count.
4. Record the failed command and short failure summary in `next.md`.
5. Add a concise `failed` or `blocked` note to `memory.md`.
6. Launch a Bug Hunter agent.
7. Send the Bug Hunter result to an independent Reviewer.
8. Re-integrate the accepted fix.
9. Return to `verifying`.
10. Rerun the full validation suite, not only the failed command.

After 3 failed fix attempts, mark the task `blocked` and require human direction.

## Stop Conditions

Stop the loop when any of these happens:

- all priority changes in `next.md` are implemented, reviewed, verified, and marked `done`
- the active task reaches 3 failed fix attempts
- the active task has unclear ownership
- secrets are detected
- migrations are required
- deploy changes are required
- validation cannot be run
- 60 minutes have elapsed for the current loop run

## Outputs

At the end of each verified task, the Orchestrator leaves:

- updated `next.md` task state
- a concise verified note in `memory.md`
- an updated `CHANGELOG.md` entry if user-visible behavior changed
- verifier evidence in the final report

At the end of a blocked task, the Orchestrator leaves:

- updated `next.md` blocked state
- a concise blocked note in `memory.md`
- the latest failure summary
- the exact command or condition that blocked progress

Planning-only work must not be added to `CHANGELOG.md`.
