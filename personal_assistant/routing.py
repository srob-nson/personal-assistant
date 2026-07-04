CODE_KEYWORDS = [
    "code", "script", "bug", "error", "traceback", "repo", "git",
    "diff", "patch", "function", "class", "test", "refactor",
    "shell", "bash", "filesystem", "file", "directory", "readme",
    "agents.md", "dockerfile", "ansible", "sshfs", "logseq plugin"
]


def should_use_codex(prompt):
    prompt_lower = prompt.lower()
    return any(word in prompt_lower for word in CODE_KEYWORDS)
