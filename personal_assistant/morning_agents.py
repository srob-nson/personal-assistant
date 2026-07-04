import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentSpec:
    name: str
    prompt: str
    workdir: Path
    search_enabled: bool = False


@dataclass(frozen=True)
class AgentResult:
    name: str
    status: str
    summary: str
    exit_code: int


def run_agents(specs, run_dir, timeout_seconds):
    spec_list = list(specs)
    if not spec_list:
        return []

    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    if len(spec_list) == 1:
        return [run_agent(spec_list[0], run_dir, timeout_seconds)]

    with ThreadPoolExecutor(max_workers=len(spec_list)) as executor:
        return list(
            executor.map(
                lambda spec: run_agent(spec, run_dir, timeout_seconds),
                spec_list,
            )
        )


def run_agent(spec, run_dir, timeout_seconds):
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    output_path = run_dir / f"{_safe_file_name(spec.name)}.md"

    command = ["codex"]
    if spec.search_enabled:
        command.append("--search")
    command.extend(["--ask-for-approval", "never"])
    command.extend(
        [
            "exec",
            "--sandbox",
            "read-only",
            "--cd",
            str(Path(spec.workdir)),
            "--output-last-message",
            str(output_path),
            "--color",
            "never",
            "--skip-git-repo-check",
        ]
    )
    command.append(spec.prompt)

    try:
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return AgentResult(
            spec.name,
            "timeout",
            f"Agent timed out after {timeout_seconds} seconds.",
            124,
        )
    except FileNotFoundError:
        return AgentResult(spec.name, "command_not_found", "Codex command not found: codex", 127)
    except OSError as error:
        return AgentResult(spec.name, "start_failed", f"Failed to start Codex: {error}", 1)

    summary = _read_summary(output_path, completed)
    status = "ok" if completed.returncode == 0 else "failed"
    return AgentResult(spec.name, status, summary, completed.returncode)


def _read_summary(output_path, completed):
    try:
        if output_path.exists():
            text = output_path.read_text(errors="ignore").strip()
            if text:
                return text
    except OSError:
        pass

    fallback = "\n".join(
        part.strip()
        for part in (completed.stdout, completed.stderr)
        if part and part.strip()
    )
    return fallback or "Agent produced no summary."


def _safe_file_name(name):
    safe = "".join(char if char.isalnum() or char in "-_" else "-" for char in name)
    return safe.strip("-") or "agent"
