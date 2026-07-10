# Morning Rundown Mobile Push Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Optionally deliver the final Morning Rundown to a mobile phone after the Logseq journal block is written.

**Architecture:** Add a small `ntfy` notification adapter using Python stdlib `urllib.request`, configured only by environment variables read at send time. Keep `--dry-run` network-free, preserve journal writes even when notification fails, and use metadata-only marker files to avoid duplicate pushes.

**Tech Stack:** Python 3 stdlib, `urllib.request`, `urllib.error`, `hashlib`, `unittest`.

---

## External Basis

- ntfy publishing supports HTTP `POST` or `PUT`: https://docs.ntfy.sh/publish/
- ntfy supports phone subscriptions on Android and iOS: https://docs.ntfy.sh/subscribe/phone/
- ntfy documents self-hosting, including Docker: https://docs.ntfy.sh/install/
- ntfy supports bearer-token authentication for publishing: https://docs.ntfy.sh/publish/#access-tokens
- ntfy is open source and dual licensed Apache 2.0/GPLv2: https://github.com/binwiederhier/ntfy

## File Structure

- Create `personal_assistant/morning_notify.py`: notification config, formatting, send, and delivery marker helpers.
- Modify `personal_assistant/morning.py`: call notification delivery after journal handling.
- Modify `personal_assistant/morning_journal.py`: expose generated-block extraction for notification retry without rerunning agents.
- Create `tests/test_morning_notify.py`: unit-test notification config, HTTP send behavior, and markers.
- Modify `tests/test_morning_workflow.py`: cover integration, dry-run, existing-block retry, failure, and force resend behavior.
- Modify `docs/personal-assistant.md`: document ntfy setup, cron vars, dry-run behavior, and privacy.
- Modify `docs/README.md`: mention the ntfy section in the main docs.
- Modify `CHANGELOG.md`: add an Unreleased entry.

## Task 1: Add Notification Adapter Unit Tests

**Files:**
- Create: `tests/test_morning_notify.py`

- [ ] **Step 1: Create failing tests**

Create `tests/test_morning_notify.py` with:

```python
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from personal_assistant.morning_notify import (
    NotificationConfig,
    already_delivered,
    format_notification_body,
    load_notification_config,
    mark_delivered,
    send_notification,
)


class MorningNotifyTests(unittest.TestCase):
    def test_load_config_disabled_without_url(self):
        with patch.dict(os.environ, {}, clear=True):
            config = load_notification_config()

        self.assertFalse(config.enabled)

    def test_load_config_reads_token_at_call_time(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env = {
                "HOME": temp_dir,
                "PA_RUNDOWN_NOTIFY_URL": "https://ntfy.example.com/morning",
                "PA_RUNDOWN_NOTIFY_TOKEN": "secret-token",
                "PA_RUNDOWN_NOTIFY_TIMEOUT_SECONDS": "7",
            }

            with patch.dict(os.environ, env, clear=True):
                config = load_notification_config()

        self.assertTrue(config.enabled)
        self.assertEqual(config.url, "https://ntfy.example.com/morning")
        self.assertEqual(config.token, "secret-token")
        self.assertEqual(config.timeout_seconds, 7)

    def test_format_notification_body_removes_markers_and_properties(self):
        block = (
            "<!-- pa-morning-rundown:start 2026-06-30 -->\n"
            "- ## Morning Rundown\n"
            "  pa_morning_rundown:: 2026-06-30\n"
            "  generated_at:: 2026-06-30T06:00:00+00:00\n"
            "  source_status:: logseq ok; repo ok\n"
            "  - TODO Write one focused task\n"
            "<!-- pa-morning-rundown:end 2026-06-30 -->\n"
        )

        body = format_notification_body(block)

        self.assertIn("Morning Rundown", body)
        self.assertIn("TODO Write one focused task", body)
        self.assertNotIn("pa_morning_rundown::", body)
        self.assertNotIn("source_status::", body)
        self.assertNotIn("<!--", body)

    def test_send_notification_posts_body_and_headers_with_fake_opener(self):
        requests = []

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))

            class Response:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, traceback):
                    return False

                def read(self):
                    return b"ok"

            return Response()

        config = NotificationConfig(
            enabled=True,
            url="https://ntfy.example.com/morning",
            token="secret-token",
            timeout_seconds=7,
            state_dir=Path("/tmp/unused"),
        )

        result = send_notification(config, "Body")

        self.assertTrue(result.ok)
        request, timeout = requests[0]
        self.assertEqual(timeout, 7)
        self.assertEqual(request.full_url, "https://ntfy.example.com/morning")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.headers["Title"], "Morning Rundown")
        self.assertEqual(request.headers["Authorization"], "Bearer secret-token")

    def test_send_notification_returns_failure_on_http_error(self):
        def fake_urlopen(request, timeout):
            raise HTTPError(request.full_url, 500, "server error", {}, None)

        config = NotificationConfig(
            enabled=True,
            url="https://ntfy.example.com/morning",
            token="",
            timeout_seconds=7,
            state_dir=Path("/tmp/unused"),
        )

        result = send_notification(config, "Body", urlopen=fake_urlopen)

        self.assertFalse(result.ok)
        self.assertIn("HTTP 500", result.message)

    def test_delivery_marker_skips_duplicate_body(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = NotificationConfig(
                enabled=True,
                url="https://ntfy.example.com/morning",
                token="",
                timeout_seconds=7,
                state_dir=Path(temp_dir),
            )

            self.assertFalse(already_delivered(config, "2026-06-30", "Body"))
            mark_delivered(config, "2026-06-30", "Body")
            self.assertTrue(already_delivered(config, "2026-06-30", "Body"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the new tests and verify failure**

Run:

```sh
python3 -m unittest tests.test_morning_notify
```

Expected: import failure because `personal_assistant.morning_notify` does not exist.

## Task 2: Implement `morning_notify.py`

**Files:**
- Create: `personal_assistant/morning_notify.py`

- [ ] **Step 1: Add the notification module**

Create `personal_assistant/morning_notify.py`:

```python
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen as default_urlopen


@dataclass(frozen=True)
class NotificationConfig:
    enabled: bool
    url: str
    token: str
    timeout_seconds: int
    state_dir: Path


@dataclass(frozen=True)
class NotificationResult:
    ok: bool
    message: str = ""


def load_notification_config():
    url = os.environ.get("PA_RUNDOWN_NOTIFY_URL", "").strip()
    timeout_seconds = _env_int("PA_RUNDOWN_NOTIFY_TIMEOUT_SECONDS", 10)
    state_dir = Path(
        os.environ.get(
            "PA_RUNDOWN_NOTIFY_STATE_DIR",
            str(Path.home() / ".local/state/personal-assistant/morning-rundown-notifications"),
        )
    ).expanduser()
    return NotificationConfig(
        enabled=bool(url),
        url=url,
        token=os.environ.get("PA_RUNDOWN_NOTIFY_TOKEN", "").strip(),
        timeout_seconds=timeout_seconds,
        state_dir=state_dir,
    )


def format_notification_body(block):
    lines = []
    for line in str(block).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("<!--"):
            continue
        if "::" in stripped and stripped.split("::", 1)[0] in {
            "pa_morning_rundown",
            "generated_at",
            "source_status",
        }:
            continue
        if stripped.startswith("- ## "):
            lines.append(stripped[5:])
        elif stripped.startswith("- "):
            lines.append(stripped[2:])
        else:
            lines.append(stripped)
    return "\n".join(lines).strip()


def send_notification(config, body, urlopen=default_urlopen):
    if not config.enabled:
        return NotificationResult(True, "notification disabled")
    parsed = urlparse(config.url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return NotificationResult(False, "invalid notification URL")

    data = body.encode("utf-8")
    request = Request(config.url, data=data, method="POST")
    request.add_header("Content-Type", "text/plain; charset=utf-8")
    request.add_header("Title", "Morning Rundown")
    request.add_header("Tags", "sunrise")
    if config.token:
        request.add_header("Authorization", f"Bearer {config.token}")

    try:
        with urlopen(request, timeout=config.timeout_seconds) as response:
            response.read()
    except HTTPError as error:
        return NotificationResult(False, f"HTTP {error.code} from notification server")
    except URLError as error:
        return NotificationResult(False, f"notification connection failed: {error.reason}")
    except TimeoutError:
        return NotificationResult(False, "notification timed out")
    except OSError as error:
        return NotificationResult(False, f"notification failed: {error}")

    return NotificationResult(True)


def already_delivered(config, run_date, body):
    return _marker_path(config, run_date, body).exists()


def mark_delivered(config, run_date, body):
    path = _marker_path(config, run_date, body)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("delivered\n")


def _marker_path(config, run_date, body):
    destination_hash = hashlib.sha256(config.url.encode("utf-8")).hexdigest()[:16]
    body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    safe_date = str(run_date)
    return config.state_dir / safe_date / f"{destination_hash}-{body_hash}.sent"


def _env_int(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default
```

- [ ] **Step 2: Run adapter tests and verify pass**

Run:

```sh
python3 -m unittest tests.test_morning_notify
```

Expected: all notification adapter tests pass.

## Task 3: Add Journal Block Extraction

**Files:**
- Modify: `personal_assistant/morning_journal.py`
- Modify: `tests/test_morning_journal.py`

- [ ] **Step 1: Add failing extraction test**

In `tests/test_morning_journal.py`, add `extract_journal_block` to the import list and append:

```python
    def test_extract_journal_block_returns_existing_generated_block(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            journal = Path(temp_dir) / "journals" / "2026_06_30.md"
            journal.parent.mkdir()
            journal.write_text(
                "- before\n"
                "<!-- pa-morning-rundown:start 2026-06-30 -->\n"
                "generated\n"
                "<!-- pa-morning-rundown:end 2026-06-30 -->\n"
                "- after\n"
            )

            block = extract_journal_block(journal, date(2026, 6, 30))

            self.assertEqual(
                block,
                "<!-- pa-morning-rundown:start 2026-06-30 -->\n"
                "generated\n"
                "<!-- pa-morning-rundown:end 2026-06-30 -->\n",
            )
```

- [ ] **Step 2: Implement extraction helper**

In `personal_assistant/morning_journal.py`, add:

```python
def extract_journal_block(journal_path, run_date):
    journal_path = Path(journal_path)
    if not journal_path.exists():
        return ""

    existing = journal_path.read_text(errors="ignore")
    start = _start_marker(run_date)
    end = _end_marker(run_date)
    start_index = existing.find(start)
    end_index = existing.find(end)
    if start_index == -1 or end_index == -1 or end_index <= start_index:
        return ""
    end_index += len(end)
    block = existing[start_index:end_index]
    if not block.endswith("\n"):
        block += "\n"
    return block
```

- [ ] **Step 3: Run journal tests**

Run:

```sh
python3 -m unittest tests.test_morning_journal
```

Expected: all journal tests pass.

## Task 4: Integrate Notification Delivery Into Morning Rundown

**Files:**
- Modify: `personal_assistant/morning.py`
- Modify: `tests/test_morning_workflow.py`

- [ ] **Step 1: Add failing integration tests**

Append these tests to `MorningWorkflowTests`:

```python
    def test_dry_run_does_not_send_when_notify_url_configured(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            graph_dir = Path(temp_dir)
            (graph_dir / "pages").mkdir()
            (graph_dir / "pages" / "Goals.md").write_text("- TODO Ship morning brief\n")

            def fake_run_agents(specs, run_dir, timeout_seconds):
                names = [spec.name for spec in specs]
                if names == ["reviewer"]:
                    return [AgentResult("reviewer", "ok", "- TODO Write one focused task", 0)]
                return [AgentResult(name, "ok", f"{name} summary", 0) for name in names]

            with patch("personal_assistant.morning.LOGSEQ_GRAPH_DIR", graph_dir):
                with patch("personal_assistant.morning.run_agents", fake_run_agents):
                    with patch("personal_assistant.morning.deliver_notification") as deliver:
                        result = run_morning_rundown(
                            ["--dry-run"],
                            today_func=lambda: date(2026, 6, 30),
                            now_func=lambda: datetime(2026, 6, 30, 6, 0, tzinfo=timezone.utc),
                            stdout=lambda _message: None,
                        )

            self.assertEqual(result, 0)
            deliver.assert_not_called()

    def test_successful_run_writes_journal_then_sends_notification(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            graph_dir = Path(temp_dir)
            (graph_dir / "pages").mkdir()
            (graph_dir / "pages" / "Goals.md").write_text("- TODO Ship morning brief\n")
            deliveries = []

            def fake_run_agents(specs, run_dir, timeout_seconds):
                names = [spec.name for spec in specs]
                if names == ["reviewer"]:
                    return [AgentResult("reviewer", "ok", "- TODO Write one focused task", 0)]
                return [AgentResult(name, "ok", f"{name} summary", 0) for name in names]

            def fake_deliver(run_date, block, force=False):
                deliveries.append((run_date, block, force))
                return True

            with patch("personal_assistant.morning.LOGSEQ_GRAPH_DIR", graph_dir):
                with patch("personal_assistant.morning.run_agents", fake_run_agents):
                    with patch("personal_assistant.morning.deliver_notification", fake_deliver):
                        result = run_morning_rundown(
                            [],
                            today_func=lambda: date(2026, 6, 30),
                            now_func=lambda: datetime(2026, 6, 30, 6, 0, tzinfo=timezone.utc),
                            stdout=lambda _message: None,
                        )

            self.assertEqual(result, 0)
            self.assertEqual(len(deliveries), 1)
            self.assertIn("TODO Write one focused task", deliveries[0][1])

    def test_existing_journal_block_can_send_missing_notification_without_agents(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            graph_dir = Path(temp_dir)
            (graph_dir / "pages").mkdir()
            (graph_dir / "pages" / "Goals.md").write_text("- TODO Ship morning brief\n")
            journal = graph_dir / "journals" / "2026_06_30.md"
            journal.parent.mkdir()
            journal.write_text(
                "<!-- pa-morning-rundown:start 2026-06-30 -->\n"
                "- ## Morning Rundown\n"
                "  - TODO Existing task\n"
                "<!-- pa-morning-rundown:end 2026-06-30 -->\n"
            )
            deliveries = []

            def fail_run_agents(specs, run_dir, timeout_seconds):
                raise AssertionError("agents should not run when today's marker exists")

            def fake_deliver(run_date, block, force=False):
                deliveries.append((run_date, block, force))
                return True

            with patch("personal_assistant.morning.LOGSEQ_GRAPH_DIR", graph_dir):
                with patch("personal_assistant.morning.run_agents", fail_run_agents):
                    with patch("personal_assistant.morning.deliver_notification", fake_deliver):
                        result = run_morning_rundown(
                            [],
                            today_func=lambda: date(2026, 6, 30),
                            stdout=lambda _message: None,
                        )

            self.assertEqual(result, 0)
            self.assertEqual(len(deliveries), 1)
            self.assertIn("TODO Existing task", deliveries[0][1])

    def test_notification_failure_returns_nonzero_after_journal_write(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            graph_dir = Path(temp_dir)
            (graph_dir / "pages").mkdir()
            (graph_dir / "pages" / "Goals.md").write_text("- TODO Ship morning brief\n")
            errors = []

            def fake_run_agents(specs, run_dir, timeout_seconds):
                names = [spec.name for spec in specs]
                if names == ["reviewer"]:
                    return [AgentResult("reviewer", "ok", "- TODO Write one focused task", 0)]
                return [AgentResult(name, "ok", f"{name} summary", 0) for name in names]

            with patch("personal_assistant.morning.LOGSEQ_GRAPH_DIR", graph_dir):
                with patch("personal_assistant.morning.run_agents", fake_run_agents):
                    with patch("personal_assistant.morning.deliver_notification", lambda *args, **kwargs: False):
                        result = run_morning_rundown(
                            [],
                            today_func=lambda: date(2026, 6, 30),
                            now_func=lambda: datetime(2026, 6, 30, 6, 0, tzinfo=timezone.utc),
                            stdout=lambda _message: None,
                            stderr=errors.append,
                        )

            self.assertEqual(result, 1)
            self.assertTrue((graph_dir / "journals" / "2026_06_30.md").exists())
            self.assertIn("notification failed", "\n".join(errors))
```

- [ ] **Step 2: Add imports in `morning.py`**

Add:

```python
from personal_assistant.morning_notify import (
    already_delivered,
    format_notification_body,
    load_notification_config,
    mark_delivered,
    send_notification,
)
from personal_assistant.morning_journal import extract_journal_block
```

Keep the existing morning journal imports and add `extract_journal_block` to that import group.

- [ ] **Step 3: Add `deliver_notification` helper**

Add this helper near `_unavailable_source_results`:

```python
def deliver_notification(run_date, block, force=False):
    config = load_notification_config()
    if not config.enabled:
        return True

    body = format_notification_body(block)
    if not body:
        return True
    date_text = run_date.isoformat()
    if not force and already_delivered(config, date_text, body):
        return True

    result = send_notification(config, body)
    if not result.ok:
        return False

    mark_delivered(config, date_text, body)
    return True
```

- [ ] **Step 4: Deliver existing block without rerunning agents**

Replace the early existing-block branch in `run_morning_rundown`:

```python
    if not options["force"] and has_journal_block(journal_path, run_date):
        stdout(f"Morning rundown already exists for {run_date.isoformat()}. Use --force to replace it.")
        return 0
```

with:

```python
    if not options["force"] and has_journal_block(journal_path, run_date):
        existing_block = extract_journal_block(journal_path, run_date)
        if not options["dry_run"] and not deliver_notification(run_date, existing_block, force=False):
            stderr("Morning rundown notification failed.")
            return 1
        stdout(f"Morning rundown already exists for {run_date.isoformat()}. Use --force to replace it.")
        return 0
```

- [ ] **Step 5: Deliver after a successful journal write**

After the `wrote` output branch and before the final return, add:

```python
    notification_ok = True
    if reviewer_result.status == "ok" and wrote:
        notification_ok = deliver_notification(run_date, block, force=options["force"])
        if not notification_ok:
            stderr("Morning rundown notification failed.")

    if reviewer_result.status != "ok":
        return 1
    return 0 if notification_ok else 1
```

Then remove the old final line:

```python
    return 0 if reviewer_result.status == "ok" else 1
```

- [ ] **Step 6: Run integration tests**

Run:

```sh
python3 -m unittest tests.test_morning_workflow tests.test_morning_journal tests.test_morning_notify
```

Expected: all focused tests pass.

## Task 5: Document Mobile Push

**Files:**
- Modify: `docs/personal-assistant.md`
- Modify: `docs/README.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add notification configuration docs**

In `docs/personal-assistant.md`, add a Morning Rundown subsection:

```markdown
### Mobile Push With ntfy

Morning Rundown can optionally publish the final generated task list to an ntfy
topic after the Logseq journal block is written. This uses Python stdlib HTTP
only; no new Python package is required.

Configure it with environment variables:

- `PA_RUNDOWN_NOTIFY_URL`: full ntfy topic URL, for example
  `https://ntfy.example.com/morning-rundown`
- `PA_RUNDOWN_NOTIFY_TOKEN`: optional bearer token
- `PA_RUNDOWN_NOTIFY_TIMEOUT_SECONDS`: optional timeout, default `10`
- `PA_RUNDOWN_NOTIFY_STATE_DIR`: optional delivery marker directory

`--dry-run` never sends a mobile notification. If today's journal block already
exists, the command can still send a missing notification without rerunning
agents. Use `--force` to regenerate the rundown and resend the notification.
```

- [ ] **Step 2: Add cron snippet**

Extend the cron environment example:

```cron
# Optional, enables ntfy mobile push:
# PA_RUNDOWN_NOTIFY_URL=https://ntfy.example.com/morning-rundown
# PA_RUNDOWN_NOTIFY_TOKEN=<token-if-required>
```

- [ ] **Step 3: Add privacy and troubleshooting notes**

Add:

```markdown
Notification content can include private task context from Logseq and source
agent summaries. Use a self-hosted ntfy server or a private high-entropy topic,
and prefer bearer-token auth when exposing the endpoint beyond your LAN.
```

Add troubleshooting:

```markdown
If mobile push does not arrive, confirm `PA_RUNDOWN_NOTIFY_URL` is set in the
same shell or crontab environment, the phone is subscribed to the topic, the
server is reachable from the cron host, and any bearer token is valid.
```

- [ ] **Step 4: Update docs index**

In `docs/README.md`, update the `personal-assistant.md` description so it mentions mobile push notification configuration.

- [ ] **Step 5: Add changelog entry**

Under `CHANGELOG.md` `## [Unreleased]` `### Added`, add:

```markdown
- Added optional ntfy mobile push delivery for successful morning rundowns,
  configured with `PA_RUNDOWN_NOTIFY_URL` and optional bearer-token auth.
```

- [ ] **Step 6: Run final validation**

Run:

```sh
python3 -m py_compile pa personal_assistant/*.py personal_assistant/backends/*.py
python3 -m unittest discover -s tests
./pa --help
./pa morning-rundown --help
git diff --check
```

Expected: all commands pass.

- [ ] **Step 7: Commit this change alone**

Run:

```sh
git add personal_assistant/morning.py personal_assistant/morning_journal.py personal_assistant/morning_notify.py tests/test_morning_workflow.py tests/test_morning_journal.py tests/test_morning_notify.py docs/personal-assistant.md docs/README.md CHANGELOG.md
git commit -m "Add morning rundown mobile push"
```
