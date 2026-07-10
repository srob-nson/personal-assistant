from pathlib import Path


def journal_path_for_date(graph_dir, run_date):
    return Path(graph_dir) / "journals" / f"{run_date:%Y_%m_%d}.md"


def build_journal_block(run_date, generated_at, tasks, source_statuses, weather_summary=None):
    date_text = run_date.isoformat()
    lines = [
        _start_marker(run_date),
        "- ## Morning Rundown",
        f"  pa_morning_rundown:: {date_text}",
        f"  generated_at:: {generated_at.isoformat()}",
        f"  source_status:: {'; '.join(source_statuses)}",
    ]
    weather_lines = _format_weather_summary(weather_summary)
    if weather_lines:
        lines.extend(weather_lines)

    task_lines = [_format_task_line(task) for task in tasks if str(task).strip()]
    if not task_lines:
        task_lines = ["  - No focused tasks generated."]
    lines.extend(task_lines)
    lines.append(_end_marker(run_date))
    return "\n".join(lines) + "\n"


def upsert_journal_block(journal_path, run_date, block, force=False):
    journal_path = Path(journal_path)
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    start = _start_marker(run_date)
    end = _end_marker(run_date)

    existing = ""
    if journal_path.exists():
        existing = journal_path.read_text(errors="ignore")

    start_index = existing.find(start)
    end_index = existing.find(end)
    if start_index != -1 and end_index != -1 and end_index > start_index:
        if not force:
            return False
        end_index += len(end)
        updated = existing[:start_index] + block + existing[end_index:]
    else:
        prefix = existing
        if prefix and not prefix.endswith("\n"):
            prefix += "\n"
        updated = prefix + block

    journal_path.write_text(updated)
    return True


def has_journal_block(journal_path, run_date):
    journal_path = Path(journal_path)
    if not journal_path.exists():
        return False

    existing = journal_path.read_text(errors="ignore")
    start_index = existing.find(_start_marker(run_date))
    end_index = existing.find(_end_marker(run_date))
    return start_index != -1 and end_index != -1 and end_index > start_index


def _format_task_line(task):
    lines = [line.strip() for line in str(task).strip().splitlines() if line.strip()]
    if not lines:
        return ""

    first = lines[0]
    if first.startswith("- "):
        formatted = [f"  {first}"]
    elif first.startswith("TODO "):
        formatted = [f"  - {first}"]
    else:
        formatted = [f"  - TODO {first}"]

    formatted.extend(f"    {line}" for line in lines[1:])
    return "\n".join(formatted)


def _format_weather_summary(weather_summary):
    if not str(weather_summary or "").strip():
        return []
    lines = ["  - Weather"]
    for line in str(weather_summary).splitlines():
        text = line.strip()
        if not text:
            continue
        if text.startswith("- "):
            text = text[2:].strip()
        lines.append(f"    - {text}")
    return lines


def _start_marker(run_date):
    return f"<!-- pa-morning-rundown:start {run_date.isoformat()} -->"


def _end_marker(run_date):
    return f"<!-- pa-morning-rundown:end {run_date.isoformat()} -->"
