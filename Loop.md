# Loop: implement-new

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

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

Active and tracked durable task records in `next.md` must use the task-state format documented there. Priority-list items may remain as plain backlog entries until the Orchestrator starts or updates them, at which point the item is converted into a durable task record. The canonical fields are:

- `id`: stable task id, such as `PA-001`
- `priority`: integer priority order
- `title`: short task title
- `status`: one of the allowed statuses above
- `plan_attempts`: integer, starting at `0`
- `implementation_attempts`: integer, starting at `0`
- `fix_attempts`: integer, starting at `0`
- `validation_result`: `not_run`, `passed`, `failed`, `preflight_failed`, or `blocked`
- `latest_failure_summary`: `none` or one concise failure summary
- `changelog_status`: `not_needed`, `planned`, `updated`, or `blocked`
- `memory_status`: `not_needed`, `planned`, `updated`, or `blocked`
- `baseline`: base `HEAD`, scoped status summary, repo-wide dirty summary, and materialization notes
- `evidence`: before/after command evidence and verifier report references

Use this Markdown shape for each durable task record:

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

## Preflight

At the start of each task, the Orchestrator records the baseline state.

Run these commands from the Git root, `/home/jellyfish/homelab`:

```sh
git rev-parse HEAD
git status --short
git status --short -- personal-assistant
git diff --stat -- personal-assistant
git ls-files --others --exclude-standard -- personal-assistant
```

Record repo-wide dirty state as a summary only. Dirty paths outside `personal-assistant` are outside the implementation scope unless the active task explicitly includes them. Record the current outside-scope dirty paths in the task baseline instead of treating them as candidate changes.

Record `personal-assistant` scoped state explicitly, including tracked diffs, diffstat, and untracked files.

Dirty files are baseline input, not completed work.

If preflight is unclear, contains secrets, includes deploy or migration changes, or has ownership conflicts, mark the task `blocked` and ask for human direction.

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

The Orchestrator accepts the Planner output when it is complete, scoped to the active task, compatible with the preflight baseline, and includes enough verification detail for a separate Verifier to execute it.

Human approval is required before implementation if the plan includes destructive commands, secret handling, deploy or migration work, external writes, changes outside the approved scope, or unresolved ownership conflicts.

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

Materialize candidates without destructive commands:

1. Capture base `HEAD` from preflight.
2. Save the scoped tracked diff for `personal-assistant`.
3. Save the list of scoped untracked files under `personal-assistant`.
4. Create each isolated tree from the same base `HEAD`, for example with `git worktree add` to a candidate path under `/tmp` or another approved scratch location.
5. Apply the same scoped tracked diff to each candidate tree.
6. Copy the same scoped untracked files into each candidate tree, preserving relative paths.
7. Record the candidate path, base `HEAD`, applied diff artifact, and copied untracked file list in `next.md`.

Do not use `git reset --hard`, `git checkout --`, `git clean`, or equivalent destructive cleanup to create or reset candidate state unless a human explicitly approves that action.

Implementers must:

- start with tests for behavior changes
- for docs, process, and tracking-only tasks, capture before/after command evidence instead of forcing behavior tests
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
git status --short
git diff --name-only
git diff --check
```

For docs, process, and tracking-only tasks, the Verifier may skip code-specific commands only if the task plan explicitly marks them irrelevant. It must still run useful state and diff checks, including `git status --short`, `git diff --name-only`, and `git diff --check`.

Add task-specific reference greps only when a future task explicitly asks for those checks.

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
- `git status --short`
- `git diff --stat`
- `git diff --name-only`
- out-of-scope dirty paths reported separately from selected candidate changes when repo-wide status or name-only output includes them
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

If preflight fails before implementation:

1. Mark the task `blocked`.
2. Set validation to `preflight_failed`.
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
