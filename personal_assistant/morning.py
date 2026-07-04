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
    RUNDOWN_WEATHER_LOCATION,
)
from personal_assistant.morning_agents import AgentResult, AgentSpec, run_agents
from personal_assistant.morning_journal import (
    build_journal_block,
    has_journal_block,
    journal_path_for_date,
    upsert_journal_block,
)


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
        source_results = source_results + _unavailable_source_results()

        reviewer_spec = _build_reviewer_spec(source_results)
        reviewer_results = run_agents([reviewer_spec], run_dir, RUNDOWN_AGENT_TIMEOUT_SECONDS)
        reviewer_result = reviewer_results[0]

    all_results = source_results + reviewer_results
    source_statuses = [f"{result.name} {result.status}" for result in all_results]
    tasks = _extract_tasks(reviewer_result.summary, RUNDOWN_TASK_LIMIT)
    if reviewer_result.status != "ok":
        tasks = [f"Review failed morning rundown agent output: {reviewer_result.summary}"]

    block = build_journal_block(
        run_date=run_date,
        generated_at=generated_at,
        tasks=tasks,
        source_statuses=source_statuses,
    )

    if options["dry_run"]:
        stdout(block.rstrip())
        return 0 if reviewer_result.status == "ok" else 1

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

    return 0 if reviewer_result.status == "ok" else 1


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
    if RUNDOWN_WEATHER_LOCATION:
        specs.append(
            AgentSpec(
                name="weather",
                workdir=Path(ASSISTANT_DIR),
                search_enabled=True,
                prompt=_weather_prompt(),
            )
        )
    return specs


def _build_reviewer_spec(source_results):
    source_text = "\n\n".join(
        f"## {result.name} ({result.status})\n{result.summary}"
        for result in source_results
    )
    prompt = f"""
You are the final reviewer for Sam's morning rundown.

Use the source-agent reports below to produce {RUNDOWN_TASK_LIMIT} or fewer focused, specific Logseq TODO items.
Each task must be actionable today, tied to goals or current context where possible, and short enough to scan in a journal.
Do not include raw source dumps, secrets, or generic wellness advice.

Return only markdown task bullets. Prefer this shape:
- TODO Concrete task
  source:: [[Goals]]
  why:: Brief reason

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


def _weather_prompt():
    location = RUNDOWN_WEATHER_LOCATION
    return f"""
You are a weather source agent for a morning rundown.

Use web search to summarize today's local weather for: {location}
Return only practical planning details such as rain, temperature range, wind, travel disruption, and daylight concerns.
""".strip()


def _unavailable_source_results():
    if RUNDOWN_WEATHER_LOCATION:
        return []
    return [
        AgentResult(
            "weather",
            "unavailable",
            "PA_RUNDOWN_WEATHER_LOCATION is not set; weather was not searched.",
            0,
        )
    ]


def _repo_paths():
    paths = []
    for value in RUNDOWN_REPOS.split(":"):
        value = value.strip()
        if value:
            paths.append(Path(value).expanduser())
    return paths


def _extract_tasks(summary, limit):
    tasks = []
    for line in str(summary).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- TODO ") or stripped.startswith("TODO "):
            tasks.append(stripped)
        elif stripped.startswith("- [ ] "):
            tasks.append("- TODO " + stripped[6:].strip())
        if len(tasks) >= limit:
            break

    if tasks:
        return tasks

    fallback = str(summary).strip()
    if fallback:
        return [fallback.splitlines()[0]]
    return []
