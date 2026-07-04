import json
import sys

from personal_assistant.config import (
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT_SECONDS,
    OLLAMA_URL,
)
from personal_assistant.context import build_ollama_system_prompt


def stream_ollama_messages(requests, messages):
    payload = {
        "model": OLLAMA_MODEL,
        "stream": True,
        "messages": [dict(message) for message in messages],
    }
    assistant_parts = []

    try:
        with requests.post(
            OLLAMA_URL,
            json=payload,
            stream=True,
            timeout=OLLAMA_TIMEOUT_SECONDS,
        ) as response:
            response.raise_for_status()

            for line in response.iter_lines():
                if not line:
                    continue

                chunk = json.loads(line.decode("utf-8"))

                if not isinstance(chunk, dict):
                    print(
                        "Ollama returned malformed stream: expected JSON object with optional message object.",
                        file=sys.stderr,
                    )
                    return 1, "", "malformed_stream"

                if "message" in chunk:
                    message = chunk["message"]
                    if not isinstance(message, dict):
                        print(
                            "Ollama returned malformed stream: expected JSON object with optional message object.",
                            file=sys.stderr,
                        )
                        return 1, "", "malformed_stream"

                    if "content" in message:
                        content = message["content"]
                        if not isinstance(content, str):
                            print(
                                "Ollama returned malformed stream: expected JSON object with optional message object.",
                                file=sys.stderr,
                            )
                            return 1, "", "malformed_stream"
                        assistant_parts.append(content)
                        print(content, end="", flush=True)

                if chunk.get("done"):
                    print()
                    return 0, "".join(assistant_parts), None
    except requests.exceptions.RequestException as error:
        print(f"Ollama request failed: {error}", file=sys.stderr)
        return 1, "", "request_failed"
    except json.JSONDecodeError as error:
        print(f"Ollama returned invalid JSON: {error}", file=sys.stderr)
        return 1, "", "invalid_json"

    print("Ollama stream ended before completion.", file=sys.stderr)
    return 1, "", "incomplete_stream"


def run_ollama(prompt, recorder=None, pa_session_id=None):
    try:
        import requests
    except ModuleNotFoundError:
        message = "Ollama backend requires the Python package 'requests'."
        print(message, file=sys.stderr)
        record_ollama_status(recorder, pa_session_id, 1, "missing_requests", message)
        return 1

    messages = [
        {
            "role": "system",
            "content": build_ollama_system_prompt()
        },
        {
            "role": "user",
            "content": prompt
        }
    ]

    print("-> Routed to Ollama. Generating response...\n", flush=True)

    turn = 1
    while True:
        try:
            result, assistant_text, status = stream_ollama_messages(requests, messages)
        except KeyboardInterrupt:
            message = "Interrupted."
            print(message, file=sys.stderr)
            record_ollama_status(recorder, pa_session_id, turn, "interrupted", message)
            return 130

        if result != 0:
            record_ollama_status(
                recorder,
                pa_session_id,
                turn,
                status or "failed",
                f"Ollama backend failed with status: {status or 'failed'}.",
            )
            return result

        record_ollama_output(recorder, pa_session_id, turn, assistant_text)
        messages.append({"role": "assistant", "content": assistant_text})

        while True:
            try:
                followup = input("Follow-up (type exit to quit): ")
            except EOFError:
                return 0
            except KeyboardInterrupt:
                message = "Interrupted."
                print(message, file=sys.stderr)
                record_ollama_status(recorder, pa_session_id, turn, "interrupted", message)
                return 130

            if followup == "exit":
                return 0

            if not followup.strip():
                continue

            turn += 1
            record_ollama_followup(recorder, pa_session_id, turn, followup)
            messages.append({"role": "user", "content": followup})
            break


def record_ollama_output(recorder, pa_session_id, turn, body):
    if recorder is None:
        return
    recorder.record("output", "ollama", body, pa_session_id or "unknown", turn)


def record_ollama_followup(recorder, pa_session_id, turn, body):
    if recorder is None:
        return
    recorder.record("follow-up", "ollama", body, pa_session_id or "unknown", turn)


def record_ollama_status(recorder, pa_session_id, turn, status, body):
    if recorder is None:
        return
    recorder.record(
        "status",
        "ollama",
        body,
        pa_session_id or "unknown",
        turn,
        status=status,
    )
