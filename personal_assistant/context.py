from dataclasses import dataclass
from pathlib import Path

from .config import (
    AGENTS_CHAR_CAP as CONTEXT_AGENTS_CHAR_CAP,
    DEFAULT_CONTEXT_SECTION_CHAR_CAP as CONTEXT_SECTION_CHAR_CAP,
    MEMORY_CHAR_CAP as CONTEXT_MEMORY_CHAR_CAP,
    MEMORY_FILE,
    PROFILE_CHAR_CAP as CONTEXT_PROFILE_CHAR_CAP,
    PROFILE_FILE,
)


@dataclass
class ContextSection:
    label: str
    path: Path
    text: str
    source_chars: int
    missing: bool
    truncated: bool
    char_cap: int

    @property
    def header(self):
        status = "missing" if self.missing else "present"
        truncation = f"truncated to {self.char_cap}" if self.truncated else "full"
        return f"[{self.label} | source={self.path} | chars={self.source_chars} | {status} | {truncation}]"

    @property
    def rendered_text(self):
        if self.truncated:
            return f"{self.text}\n[TRUNCATED from {self.source_chars} to {self.char_cap} chars]"
        return self.text


def read_file(path):
    try:
        if path.exists():
            return path.read_text(errors="ignore")
    except OSError:
        return ""
    return ""


def build_context(user_prompt):
    return "\n".join(
        [
            "You are Sam's local CLI Personal Assistant.",
            "",
            render_sections(collect_context_sections()),
            "USER PROMPT:",
            user_prompt,
        ]
    ).strip()


def build_ollama_system_prompt():
    return "\n".join(
        [
            "You are Sam's local CLI Personal Assistant.",
            "",
            render_sections(collect_context_sections()),
        ]
    ).strip()


def build_context_preview(user_prompt):
    return (
        "Codex shape:\n"
        f"{build_context(user_prompt)}\n\n"
        "Ollama shape:\n"
        "role=system\n"
        f"{build_ollama_system_prompt()}\n\n"
        "role=user\n"
        f"{user_prompt}"
    ).strip()


def collect_context_sections():
    agents_file = Path.cwd() / "AGENTS.md"
    return [
        load_context_section("PROFILE", PROFILE_FILE, CONTEXT_PROFILE_CHAR_CAP),
        load_context_section("MEMORY", MEMORY_FILE, CONTEXT_MEMORY_CHAR_CAP),
        load_context_section("PROJECT CONTEXT", agents_file, CONTEXT_AGENTS_CHAR_CAP),
    ]


def load_context_section(label, path, section_cap):
    raw_text = read_file(path)
    source_chars = len(raw_text)
    char_cap = min(CONTEXT_SECTION_CHAR_CAP, section_cap)
    truncated = source_chars > char_cap
    text = raw_text[:char_cap] if truncated else raw_text
    return ContextSection(
        label=label,
        path=path,
        text=text,
        source_chars=source_chars,
        missing=not path.exists(),
        truncated=truncated,
        char_cap=char_cap,
    )


def render_sections(sections):
    parts = []
    for section in sections:
        parts.extend(
            [
                section.header,
                f"{section.label}:",
                section.rendered_text,
                "",
            ]
        )
    return "\n".join(parts).rstrip()
