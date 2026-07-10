import sys
import uuid

from personal_assistant.backends.codex import run_codex
from personal_assistant.backends.ollama import run_ollama
from personal_assistant.context import build_context, build_context_preview
from personal_assistant.logseq import LogseqRecorder
from personal_assistant.morning import run_morning_rundown
from personal_assistant.routing import should_use_codex


class UsageError(Exception):
    pass


def print_usage():
    print('Usage: pa [--context-preview] [-c|-o] [-l] "prompt here"')
    print("       pa morning-rundown [--dry-run] [--force]")
    print()
    print("Routes coding-related prompts to Codex and other prompts to Ollama.")
    print("Use --context-preview to print the local context sent to each backend.")
    print("Use -c or -o to force a backend.")
    print("Use -l to capture prompts and outputs in Logseq.")
    print("Use morning-rundown to write a 6am planning brief to today's Logseq journal.")


def new_session_id():
    return str(uuid.uuid4())


def parse_args(args):
    if not args:
        raise UsageError()

    context_preview = False
    route_override = None
    logseq_enabled = False
    index = 0

    while index < len(args):
        arg = args[index]

        if arg in ("-h", "--help"):
            return True, False, None, False, []

        if arg in ("--codex", "--ollama"):
            raise UsageError()

        if arg == "--context-preview":
            context_preview = True
            index += 1
            continue

        if arg == "-l":
            logseq_enabled = True
            index += 1
            continue

        if arg in ("-c", "-o"):
            route = "codex" if arg == "-c" else "ollama"
            if route_override and route_override != route:
                raise UsageError()
            route_override = route
            index += 1
            continue

        if arg.startswith("-"):
            raise UsageError()

        break

    prompt_args = args[index:]
    if not prompt_args:
        raise UsageError()

    return False, context_preview, route_override, logseq_enabled, prompt_args


def main(argv=None):
    if argv is None:
        argv = sys.argv

    if len(argv) > 1 and argv[1] == "morning-rundown":
        return run_morning_rundown(argv[2:])

    try:
        show_help, context_preview, route_override, logseq_enabled, prompt_args = parse_args(
            argv[1:]
        )
    except UsageError:
        print_usage()
        return 1

    if show_help:
        print_usage()
        return 0

    user_prompt = " ".join(prompt_args)
    if context_preview:
        print(build_context_preview(user_prompt))
        return 0

    route = route_override
    if route is None:
        route = "codex" if should_use_codex(user_prompt) else "ollama"

    recorder = None
    pa_session_id = None
    if logseq_enabled:
        recorder = LogseqRecorder()
        pa_session_id = new_session_id()
        recorder.record("prompt", route, user_prompt, pa_session_id, 1)

    if route == "codex":
        return run_codex(
            build_context(user_prompt),
            recorder=recorder,
            pa_session_id=pa_session_id,
        )

    return run_ollama(user_prompt, recorder=recorder, pa_session_id=pa_session_id)
