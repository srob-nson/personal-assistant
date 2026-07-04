from pathlib import Path

from .config import MEMORY_FILE, PROFILE_FILE


def read_file(path):
    if path.exists():
        return path.read_text(errors="ignore")
    return ""


def build_context(user_prompt):
    profile = read_file(PROFILE_FILE)
    memory = read_file(MEMORY_FILE)

    agents_file = Path.cwd() / "AGENTS.md"
    agents = read_file(agents_file)

    return f"""
You are Sam's local CLI Personal Assistant.

PROFILE:
{profile}

MEMORY:
{memory}

PROJECT CONTEXT:
{agents}

USER PROMPT:
{user_prompt}
""".strip()


def build_ollama_system_prompt():
    profile = read_file(PROFILE_FILE)
    memory = read_file(MEMORY_FILE)

    agents_file = Path.cwd() / "AGENTS.md"
    agents = read_file(agents_file)

    return f"""
You are Sam's local CLI Personal Assistant.

PROFILE:
{profile}

MEMORY:
{memory}

PROJECT CONTEXT:
{agents}
""".strip()
