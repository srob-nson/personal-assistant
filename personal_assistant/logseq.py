import getpass
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from personal_assistant.config import LOGSEQ_GRAPH_DIR


PROMPT_KINDS = {"prompt", "follow-up"}


class LogseqRecorder:
    def __init__(self, graph_dir=LOGSEQ_GRAPH_DIR, username=None, now_func=None, stderr=None):
        self.graph_dir = Path(graph_dir).expanduser()
        self.username = username or getpass.getuser()
        self.now_func = now_func or (lambda: datetime.now(timezone.utc))
        self.stderr = stderr or sys.stderr
        self.enabled = True

        if not self.graph_dir.is_dir():
            self.enabled = False
            self._warn(f"Logseq capture disabled: graph directory not found: {self.graph_dir}")

    def record(self, kind, route, body, session_id, turn, status=None, metadata=None):
        if not self.enabled:
            return

        page_name = "Prompts.md" if kind in PROMPT_KINDS else "Outputs.md"
        page_path = self.graph_dir / "pages" / page_name

        try:
            page_path.parent.mkdir(exist_ok=True)
            entry = self._format_entry(
                kind=kind,
                route=route,
                body=body,
                session_id=session_id,
                turn=turn,
                status=status,
                metadata=metadata or {},
            )
            self._append_entry(page_path, entry)
        except OSError as error:
            self._warn(f"Logseq capture warning: {error}")

    def _format_entry(self, kind, route, body, session_id, turn, status, metadata):
        timestamp = self.now_func().astimezone(timezone.utc).isoformat()
        parts = [
            timestamp,
            f"session `{session_id}`",
            f"turn `{turn}`",
            f"route `{route}`",
            f"kind `{kind}`",
            f"user `{self.username}`",
        ]
        if status:
            parts.append(f"status `{status}`")

        body_text = "" if body is None else str(body)
        fence = self._fence_for(body_text)
        lines = [f"- {' | '.join(parts)}", f"  {fence}text"]
        body_lines = body_text.splitlines()
        if not body_lines:
            body_lines = [""]
        lines.extend(f"  {line}" for line in body_lines)
        lines.append(f"  {fence}")

        for key in sorted(metadata):
            lines.append(f"  - {key}:: {self._format_metadata_value(key, metadata[key])}")

        return "\n".join(lines) + "\n"

    def _fence_for(self, body):
        runs = [len(match.group(0)) for match in re.finditer(r"`+", body)]
        fence_length = max([3] + [run + 1 for run in runs])
        return "`" * fence_length

    def _format_metadata_value(self, key, value):
        if value is None:
            return ""
        if key.endswith("_command"):
            return f"`{value}`"
        return str(value)

    def _append_entry(self, page_path, entry):
        prefix = ""
        if page_path.exists() and page_path.stat().st_size > 0:
            with page_path.open("rb") as page:
                page.seek(-1, 2)
                if page.read(1) != b"\n":
                    prefix = "\n"

        with page_path.open("a", encoding="utf-8") as page:
            page.write(prefix + entry)

    def _warn(self, message):
        print(message, file=self.stderr)
