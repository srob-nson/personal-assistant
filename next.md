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

Reviewer check applied: these five suggestions were narrowed against the
current code, docs, tests, and dirty working tree. They stay as plain backlog
items until an Orchestrator starts one and converts it into the durable task
record format above.

### PA-001: Add context privacy controls and preview

- priority: 1
- status: done
- plan_attempts: 1
- implementation_attempts: 1
- fix_attempts: 1
- validation_result: passed
- latest_failure_summary: none
- changelog_status: updated
- memory_status: updated
- baseline: base `d068d0259b5226f09365dbf3c8e4dba3b9998cb1`; scoped dirty tracked files `CHANGELOG.md`, `Loop.md`, `docs/personal-assistant.md`, `next.md`, `personal_assistant/config.py`, `personal_assistant/morning.py`, `personal_assistant/morning_journal.py`, `tests/test_morning_journal.py`, `tests/test_morning_workflow.py`; scoped untracked files `docs/2026-07-07-morning-mobile-push.md`, `docs/adding-weather.md`, `personal_assistant/morning_weather.py`, `tests/test_config.py`, `tests/test_morning_weather.py`; scoped diffstat 9 files, 473 insertions, 125 deletions; outside-scope dirty paths `.Trash-1000/`, `claude-desktop_amd64.deb`; materialization via two isolated worker candidates.
- evidence: implemented capped and labeled context sections, `pa --context-preview`, backend-shape preview output, raw-prompt Logseq preservation, and `PA_*` context cap tests. Implementer reports `019f485d-73df-7f83-8df3-dbfa31118ef8` and `019f485d-a671-74b2-b5e6-8b532ac57123` completed with red/green evidence. Reviewer `019f4862-e441-70e0-b372-ba5dd2caaa26` rejected the first diff package because it included dirty-baseline morning-rundown config changes and test gaps; fix attempt 1 added CLI-level real preview plus preview-with-`-l` coverage and `PA_*` cap parser tests. A second subagent reviewer could not run because subagent quota was exhausted, so the Orchestrator performed a local baseline-aware review. Verifier evidence: `python3 -m py_compile pa personal_assistant/*.py personal_assistant/backends/*.py` exit 0; `python3 -m unittest discover -s tests` exit 0 with 90 tests OK; `./pa --help` exit 0 with usage `Usage: pa [--context-preview] [-c|-o] [-l] "prompt here"`; `./pa morning-rundown --help` exit 0 with usage `Usage: pa morning-rundown [--dry-run] [--force]`; `git status --short` and `git diff --name-only` recorded candidate plus baseline dirty paths; `git diff --check` exit 0; `PA_CONTEXT_SECTION_CHAR_CAP=3 ./pa --context-preview hello` exit 0 showed source paths, character counts, truncation to 3 chars, `USER PROMPT`, `role=system`, and `role=user`.

2. Add explainable safer routing.
   Replace broad substring routing with word-aware and phrase-aware route
   rules, then add `pa --route-preview "prompt"` to print deterministic route
   data: selected backend, override state, matched rule ids, and matched text.
   Preserve `-c` and `-o` as concise forced-route overrides.

   Implementation notes: avoid casual false positives such as `classical
   music`, `file this idea`, or `contest`, while preserving real coding
   prompts such as `review this repository`, `fix this test`, and
   `update AGENTS.md`.

   Validation notes: add routing-table tests for positive matches, false
   positives, forced overrides, preview output, and old rejected long flags.

3. Harden the main Codex backend with explicit execution profiles.
   Make normal Codex routing more deterministic without breaking the current
   manual coding workflow. Keep the default interactive flow unless an explicit
   exec profile is selected, but share or extract the existing morning-agent
   Codex command resolution so `PA_CODEX_COMMAND`, `PATH`, and
   `$HOME/.local/bin/codex` behave consistently across both Codex paths.

   Implementation notes: add documented `interactive` and `exec` profiles,
   explicit working directory handling, practical timeout/error behavior where
   appropriate, and richer Logseq status metadata for the exact profile and
   command shape used. The `exec` profile should use read-only defaults unless
   the user explicitly chooses a broader mode.

   Validation notes: fake `subprocess.run` and assert command construction,
   profile selection, configured-command resolution, exit-code propagation,
   missing-command handling, timeout handling, and status capture.

4. Implement open-source mobile push for Morning Rundown.
   Turn the existing ntfy design into an optional delivery feature that sends
   the final generated Morning Rundown to a phone after a successful journal
   write. Configure it with `PA_RUNDOWN_NOTIFY_URL`, optional bearer token,
   timeout, and state directory. Use Python stdlib `urllib.request`; do not add
   another runtime dependency.

   Implementation notes: keep `--dry-run` network-free, keep the Logseq
   journal write as the primary output, return a degraded nonzero status only
   after the journal write succeeds and notification delivery fails, and use a
   separate notification delivery marker keyed by date/body hash. The existing
   journal block markers remain the source of generated content.

   Validation notes: add fake-`urlopen` notification tests, marker dedupe tests,
   dry-run no-network tests, existing-block retry tests, forced resend behavior,
   and docs for self-hosted or private-topic ntfy setup.

5. Add daily review and task rollover.
   Let `pa morning-rundown` read yesterday's generated journal block plus the
   current Logseq task state, then summarize completed, stale, and blocked
   items before today's reviewer prompt runs. This is a rollover review, not a
   replacement for the existing source-agent instruction to skip `DONE` tasks.

   Implementation notes: extract only the prior generated block by marker,
   compare previous TODO text and metadata against current Logseq pages, pass a
   compact rollover summary into the reviewer, and require explicit rollover
   reasons so completed tasks are not re-emitted as new work.

   Validation notes: use temporary Logseq graphs and fake source/reviewer
   agents to cover completed tasks, stale tasks, blocked tasks, missing prior
   journal blocks, and the five-task cap.

## Suggested Validation

- `python3 -m py_compile pa personal_assistant/*.py personal_assistant/backends/*.py`
- `python3 -m unittest discover -s tests`
- `./pa --help`
- `./pa morning-rundown --help`
- `git diff --check`

## Short Prompt For A New Agent

You are working in `/home/jellyfish/homelab/personal-assistant`. Read `AGENTS.md` and `next.md` first. Implement the priority changes in `next.md` conservatively, keeping `pa` as a thin launcher and preserving the existing concise CLI style. Start with tests for each behavior change, do not contact real Ollama or Codex in automated tests, and do not revert unrelated dirty worktree changes. Validate with `python3 -m py_compile pa personal_assistant/*.py personal_assistant/backends/*.py`, `python3 -m unittest discover -s tests`, `./pa --help`, `./pa morning-rundown --help`, and `git diff --check`.
