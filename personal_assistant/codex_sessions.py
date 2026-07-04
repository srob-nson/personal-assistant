import re
from pathlib import Path

from personal_assistant.config import CODEX_SESSIONS_DIR


SESSION_ID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)


def find_latest_codex_session_id(started_at, sessions_dir=CODEX_SESSIONS_DIR):
    root = Path(sessions_dir).expanduser()
    if not root.is_dir():
        return None

    candidates = []
    try:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            try:
                modified_at = path.stat().st_mtime
            except OSError:
                continue
            if modified_at >= started_at:
                candidates.append((modified_at, path))
    except OSError:
        return None

    for _modified_at, path in sorted(candidates, reverse=True):
        session_id = _extract_session_id(path.name)
        if session_id:
            return session_id

        try:
            session_id = _extract_session_id(path.read_text(errors="ignore")[:65536])
        except OSError:
            session_id = None
        if session_id:
            return session_id

    return None


def _extract_session_id(text):
    match = SESSION_ID_RE.search(text)
    if match:
        return match.group(0)
    return None
