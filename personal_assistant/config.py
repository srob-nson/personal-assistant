import os
from pathlib import Path


def env_int(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def env_bounded_int(name, default, minimum, maximum):
    value = env_int(name, default)
    return min(max(value, minimum), maximum)


def load_rundown_task_limit():
    return env_bounded_int("PA_RUNDOWN_TASK_LIMIT", 5, 1, 5)


def load_rundown_weather_location(location_file=None):
    if "PA_RUNDOWN_WEATHER_LOCATION" in os.environ:
        return os.environ["PA_RUNDOWN_WEATHER_LOCATION"].strip()

    if location_file is None:
        location_file = os.environ.get(
            "PA_RUNDOWN_WEATHER_LOCATION_FILE",
            str(Path.home() / ".config/personal-assistant/weather-location"),
        )
    location_path = Path(location_file).expanduser()

    try:
        lines = location_path.read_text(errors="ignore").splitlines()
    except OSError:
        return ""

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return ""


def load_context_char_cap(name, default):
    return env_bounded_int(name, default, 0, 20000)


ASSISTANT_DIR = Path.home() / "homelab/personal-assistant"
PROFILE_FILE = ASSISTANT_DIR / "profile.md"
MEMORY_FILE = ASSISTANT_DIR / "memory.md"
LOGSEQ_GRAPH_DIR = Path(
    os.environ.get("PA_LOGSEQ_GRAPH_DIR", str(Path.home() / "homelab/logseq2-0"))
).expanduser()
CODEX_SESSIONS_DIR = Path(
    os.environ.get("PA_CODEX_SESSIONS_DIR", str(Path.home() / ".codex/sessions"))
).expanduser()
RUNDOWN_REPOS = os.environ.get("PA_RUNDOWN_REPOS", str(Path.home() / "homelab"))
RUNDOWN_WEATHER_LOCATION = load_rundown_weather_location()
RUNDOWN_TASK_LIMIT = load_rundown_task_limit()
RUNDOWN_AGENT_TIMEOUT_SECONDS = env_int("PA_RUNDOWN_AGENT_TIMEOUT_SECONDS", 300)
RUNDOWN_WEATHER_TIMEOUT_SECONDS = env_int("PA_RUNDOWN_WEATHER_TIMEOUT_SECONDS", 10)

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.1:8b"
OLLAMA_TIMEOUT_SECONDS = 120

DEFAULT_CONTEXT_SECTION_CHAR_CAP = load_context_char_cap(
    "PA_CONTEXT_SECTION_CHAR_CAP",
    4000,
)
PROFILE_CHAR_CAP = load_context_char_cap(
    "PA_PROFILE_CHAR_CAP",
    DEFAULT_CONTEXT_SECTION_CHAR_CAP,
)
MEMORY_CHAR_CAP = load_context_char_cap(
    "PA_MEMORY_CHAR_CAP",
    DEFAULT_CONTEXT_SECTION_CHAR_CAP,
)
AGENTS_CHAR_CAP = load_context_char_cap(
    "PA_AGENTS_CHAR_CAP",
    DEFAULT_CONTEXT_SECTION_CHAR_CAP,
)
CONTEXT_SECTION_CHAR_CAP = DEFAULT_CONTEXT_SECTION_CHAR_CAP
CONTEXT_PROFILE_CHAR_CAP = PROFILE_CHAR_CAP
CONTEXT_MEMORY_CHAR_CAP = MEMORY_CHAR_CAP
CONTEXT_AGENTS_CHAR_CAP = AGENTS_CHAR_CAP
