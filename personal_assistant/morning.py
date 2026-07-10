import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

from personal_assistant.config import (
    ASSISTANT_DIR,
    LOGSEQ_GRAPH_DIR,
    RUNDOWN_AGENT_TIMEOUT_SECONDS,
    RUNDOWN_REPOS,
    RUNDOWN_TASK_LIMIT,
    RUNDOWN_WEATHER_TIMEOUT_SECONDS,
    RUNDOWN_WEATHER_LOCATION,
)
from personal_assistant.morning_agents import AgentSpec, run_agents
from personal_assistant.morning_journal import (
    build_journal_block,
    has_journal_block,
    journal_path_for_date,
    upsert_journal_block,
)
from personal_assistant.morning_weather import fetch_weather_summary


LOGSEQ_PAGES = ("Goals", "Tasks", "Projects")


class MorningUsageError(Exception):
    pass


def run_morning_rundown(args, today_func=None, now_func=None, stdout=None, stderr=None):
    stdout = stdout or print
    stderr = stderr or (lambda message: print(message, file=sys.stderr))
    today_func = today_func or date.today
    now_func = now_func or (lambda: datetime.now().astimezone())

    try:
        options = _parse_morning_args(args)
    except MorningUsageError:
        _print_morning_usage(stdout)
        return 1

    if options["help"]:
        _print_morning_usage(stdout)
        return 0

    graph_dir = Path(LOGSEQ_GRAPH_DIR)
    if not graph_dir.is_dir():
        stderr(f"Morning rundown failed: Logseq graph directory not found: {graph_dir}")
        return 1

    run_date = today_func()
    generated_at = now_func()
    journal_path = journal_path_for_date(graph_dir, run_date)

    if not options["force"] and has_journal_block(journal_path, run_date):
        stdout(f"Morning rundown already exists for {run_date.isoformat()}. Use --force to replace it.")
        return 0

    missing_pages = _missing_logseq_pages(graph_dir)
    if len(missing_pages) == len(LOGSEQ_PAGES):
        stderr("Morning rundown failed: none of Goals.md, Tasks.md, or Projects.md exist.")
        return 1

    with tempfile.TemporaryDirectory(prefix="pa-morning-rundown-") as run_dir_name:
        run_dir = Path(run_dir_name)
        source_specs = _build_source_specs(graph_dir)
        source_results = run_agents(source_specs, run_dir, RUNDOWN_AGENT_TIMEOUT_SECONDS)
        source_results = source_results + [
            fetch_weather_summary(
                RUNDOWN_WEATHER_LOCATION,
                RUNDOWN_WEATHER_TIMEOUT_SECONDS,
            )
        ]

        reviewer_spec = _build_reviewer_spec(source_results)
        reviewer_results = run_agents([reviewer_spec], run_dir, RUNDOWN_AGENT_TIMEOUT_SECONDS)
        reviewer_result = reviewer_results[0]

    all_results = source_results + reviewer_results
    source_statuses = [f"{result.name} {result.status}" for result in all_results]
    tasks = _extract_tasks(reviewer_result.summary, RUNDOWN_TASK_LIMIT)
    if reviewer_result.status != "ok":
        tasks = [f"Review failed morning rundown agent output: {reviewer_result.summary}"]

    degraded_results = _degraded_results(source_results)
    exit_code = 0 if reviewer_result.status == "ok" and not degraded_results else 1

    block = build_journal_block(
        run_date=run_date,
        generated_at=generated_at,
        tasks=tasks,
        source_statuses=source_statuses,
        weather_summary=_weather_summary(source_results),
    )

    if options["dry_run"]:
        stdout(block.rstrip())
        if degraded_results:
            stderr(_degraded_message(degraded_results))
        return exit_code

    wrote = upsert_journal_block(
        journal_path,
        run_date,
        block,
        force=options["force"],
    )
    if wrote:
        stdout(f"Morning rundown written to {journal_path}")
    else:
        stdout(f"Morning rundown already exists for {run_date.isoformat()}. Use --force to replace it.")

    if degraded_results:
        stderr(_degraded_message(degraded_results))
    return exit_code


def _parse_morning_args(args):
    options = {"dry_run": False, "force": False, "help": False}
    for arg in args:
        if arg in ("-h", "--help"):
            options["help"] = True
        elif arg == "--dry-run":
            options["dry_run"] = True
        elif arg == "--force":
            options["force"] = True
        else:
            raise MorningUsageError()
    return options


def _print_morning_usage(output):
    output("Usage: pa morning-rundown [--dry-run] [--force]")


def _missing_logseq_pages(graph_dir):
    return [
        page_name
        for page_name in LOGSEQ_PAGES
        if not (graph_dir / "pages" / f"{page_name}.md").exists()
    ]


def _build_source_specs(graph_dir):
    repo_paths = _repo_paths()
    first_repo = repo_paths[0] if repo_paths else Path(ASSISTANT_DIR)
    specs = [
        AgentSpec(
            name="logseq",
            workdir=graph_dir,
            search_enabled=False,
            prompt=_logseq_prompt(graph_dir),
        ),
        AgentSpec(
            name="repo",
            workdir=first_repo,
            search_enabled=False,
            prompt=_repo_prompt(repo_paths),
        ),
        AgentSpec(
            name="news",
            workdir=Path(ASSISTANT_DIR),
            search_enabled=True,
            prompt=_news_prompt(),
        ),
    ]
    return specs


def _build_reviewer_spec(source_results):
    source_text = "\n\n".join(
        f"## {result.name} ({result.status})\n{result.summary}"
        for result in source_results
    )
    prompt = f"""
You are the final reviewer for Sam's morning rundown.

Use the source-agent reports below to produce {RUNDOWN_TASK_LIMIT} or fewer ranked, outcome-focused Logseq TODO items.
Each task must be actionable today, tied to goals or current context where possible, and short enough to scan in a journal.
Combine validation, cleanup, and documentation work into the related outcome task when possible.
Avoid generic wellness advice. Avoid separate low-value housekeeping tasks unless they are blocking a more important outcome.
Do not include raw source dumps or secrets.

Return only markdown task bullets in this exact shape:
- TODO Concrete outcome for today
  source:: [[Goals]] or [[Tasks]] or [[Projects]] or repo/news/weather
  why:: One short reason this matters today
  next:: First concrete action or finish condition

SOURCE REPORTS:
{source_text}
""".strip()
    return AgentSpec(
        name="reviewer",
        workdir=Path(ASSISTANT_DIR),
        search_enabled=False,
        prompt=prompt,
    )


def _logseq_prompt(graph_dir):
    pages = "\n".join(str(graph_dir / "pages" / f"{page}.md") for page in LOGSEQ_PAGES)
    return f"""
You are a read-only Logseq source agent for a morning rundown.

Inspect only these pages if present:
{pages}

Summarize active goals, tasks, and projects that should influence today's focused tasks.
Prefer TODO, DOING, NOW, LATER, WAITING, DEADLINE, SCHEDULED, priority::, and nearby parent context.
Skip DONE, CANCELED, archived blocks, fenced code blocks, and secret-looking lines.
Do not edit files. Do not print full raw pages. Return a concise markdown summary with source page names.
""".strip()


def _repo_prompt(repo_paths):
    repos = "\n".join(str(path) for path in repo_paths) or "(no configured repos)"
    return f"""
You are a read-only repository source agent for a morning rundown.

Inspect these repositories:
{repos}

Use read-only commands such as git status --short, git log --oneline --since yesterday, and git diff --stat.
Do not edit files. Do not run package installs or formatters. Do not include raw diffs.
Return concise project-relevant changes and concrete follow-up risks.
""".strip()


def _news_prompt():
    return """
You are a breaking-news source agent for a morning rundown.

Use web search to identify the most important current world news items that could affect planning today.
Return at most five concise bullets with source names. Avoid speculation and do not include full articles.
""".strip()


def _repo_paths():
    paths = []
    for value in RUNDOWN_REPOS.split(":"):
        value = value.strip()
        if value:
            paths.append(Path(value).expanduser())
    return paths


def _degraded_results(results):
    return [
        result
        for result in results
        if result.status not in ("ok", "unavailable")
    ]


def _degraded_message(results):
    statuses = "; ".join(f"{result.name} {result.status}" for result in results)
    return f"Morning rundown degraded: {statuses}"


def _weather_summary(results):
    for result in results:
        if result.name == "weather" and result.status == "ok":
            return result.summary
    return ""


def _extract_tasks(summary, limit):
    tasks = []
    current_task = None
    for line in str(summary).splitlines():
        stripped = line.strip()
        if not stripped:
            current_task = None
            continue

        task_start = _normalise_task_start(stripped)
        if task_start:
            if len(tasks) >= limit:
                break
            current_task = [task_start]
            tasks.append(current_task)
            continue

        if current_task is not None and _is_task_detail_line(line):
            current_task.append(stripped)
        else:
            current_task = None

        if len(tasks) >= limit:
            continue

    if tasks:
        return ["\n".join(task) for task in tasks]

    fallback = str(summary).strip()
    if fallback:
        return [fallback.splitlines()[0]]
    return []


def _normalise_task_start(stripped):
    if stripped.startswith("- TODO "):
        return stripped
    if stripped.startswith("TODO "):
        return "- " + stripped
    if stripped.startswith("- [ ] "):
        return "- TODO " + stripped[6:].strip()
    return ""


def _is_task_detail_line(line):
    if line == line.lstrip():
        return False
    stripped = line.strip()
    return (
        stripped.startswith("source::")
        or stripped.startswith("why::")
        or stripped.startswith("next::")
    )
