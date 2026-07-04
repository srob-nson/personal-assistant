import getpass
import subprocess
import sys
import time

from personal_assistant.codex_sessions import find_latest_codex_session_id


def run_codex(prompt, recorder=None, pa_session_id=None):
    started_at = time.time()
    print("-> Routed to Codex. Starting coding assistant...\n", flush=True)

    try:
        result = subprocess.run(
            ["codex", prompt],
            text=True
        )
    except FileNotFoundError:
        message = "Codex command not found: codex"
        print(message, file=sys.stderr)
        record_codex_status(
            recorder,
            pa_session_id,
            status="command_not_found",
            body=message,
            exit_code=127,
        )
        return 127
    except OSError as error:
        message = f"Failed to start Codex: {error}"
        print(message, file=sys.stderr)
        record_codex_status(
            recorder,
            pa_session_id,
            status="start_failed",
            body=message,
            exit_code=1,
        )
        return 1

    codex_session_id = find_latest_codex_session_id(started_at)
    body = f"Codex exited with status {result.returncode}."
    if codex_session_id:
        body = f"{body} Resume with: codex resume {codex_session_id}"
    status = "completed" if result.returncode == 0 else "failed"
    record_codex_status(
        recorder,
        pa_session_id,
        status=status,
        body=body,
        exit_code=result.returncode,
        codex_session_id=codex_session_id,
    )

    return result.returncode


def record_codex_status(
    recorder,
    pa_session_id,
    status,
    body,
    exit_code,
    codex_session_id=None,
):
    if recorder is None:
        return

    metadata = {
        "exit_code": exit_code,
        "launcher_user": getpass.getuser(),
    }
    if codex_session_id:
        metadata["codex_session_id"] = codex_session_id
        metadata["resume_command"] = f"codex resume {codex_session_id}"

    recorder.record(
        "status",
        "codex",
        body,
        pa_session_id or "unknown",
        1,
        status=status,
        metadata=metadata,
    )
