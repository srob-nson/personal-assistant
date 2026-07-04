import os
from pathlib import Path


def env_int(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


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
RUNDOWN_WEATHER_LOCATION = os.environ.get("PA_RUNDOWN_WEATHER_LOCATION", "")
RUNDOWN_TASK_LIMIT = env_int("PA_RUNDOWN_TASK_LIMIT", 7)
RUNDOWN_AGENT_TIMEOUT_SECONDS = env_int("PA_RUNDOWN_AGENT_TIMEOUT_SECONDS", 300)

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.1:8b"
OLLAMA_TIMEOUT_SECONDS = 120
