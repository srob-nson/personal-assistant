import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from personal_assistant.config import (
    load_context_char_cap,
    load_rundown_task_limit,
    load_rundown_weather_location,
)


class ConfigTests(unittest.TestCase):
    def test_weather_location_env_overrides_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            location_file = Path(temp_dir) / "weather-location"
            location_file.write_text("Folkestone, UK\n")

            with patch.dict(os.environ, {"PA_RUNDOWN_WEATHER_LOCATION": "London"}, clear=True):
                result = load_rundown_weather_location(location_file)

        self.assertEqual(result, "London")

    def test_empty_weather_location_env_disables_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            location_file = Path(temp_dir) / "weather-location"
            location_file.write_text("Folkestone, UK\n")

            with patch.dict(os.environ, {"PA_RUNDOWN_WEATHER_LOCATION": ""}, clear=True):
                result = load_rundown_weather_location(location_file)

        self.assertEqual(result, "")

    def test_weather_location_reads_first_non_comment_file_line(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            location_file = Path(temp_dir) / "weather-location"
            location_file.write_text("\n# local weather location\nFolkestone, UK\n")

            with patch.dict(os.environ, {}, clear=True):
                result = load_rundown_weather_location(location_file)

        self.assertEqual(result, "Folkestone, UK")

    def test_missing_weather_location_file_returns_empty_string(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            location_file = Path(temp_dir) / "missing"

            with patch.dict(os.environ, {}, clear=True):
                result = load_rundown_weather_location(location_file)

        self.assertEqual(result, "")

    def test_rundown_task_limit_defaults_to_five(self):
        with patch.dict(os.environ, {}, clear=True):
            result = load_rundown_task_limit()

        self.assertEqual(result, 5)

    def test_invalid_rundown_task_limit_uses_default(self):
        with patch.dict(os.environ, {"PA_RUNDOWN_TASK_LIMIT": "many"}, clear=True):
            result = load_rundown_task_limit()

        self.assertEqual(result, 5)

    def test_high_rundown_task_limit_is_capped_at_five(self):
        with patch.dict(os.environ, {"PA_RUNDOWN_TASK_LIMIT": "9"}, clear=True):
            result = load_rundown_task_limit()

        self.assertEqual(result, 5)

    def test_low_rundown_task_limit_is_raised_to_one(self):
        with patch.dict(os.environ, {"PA_RUNDOWN_TASK_LIMIT": "0"}, clear=True):
            result = load_rundown_task_limit()

        self.assertEqual(result, 1)

    def test_context_char_cap_reads_pa_environment_value(self):
        with patch.dict(os.environ, {"PA_PROFILE_CHAR_CAP": "123"}, clear=True):
            result = load_context_char_cap("PA_PROFILE_CHAR_CAP", 4000)

        self.assertEqual(result, 123)

    def test_context_char_cap_invalid_value_uses_default(self):
        with patch.dict(os.environ, {"PA_MEMORY_CHAR_CAP": "many"}, clear=True):
            result = load_context_char_cap("PA_MEMORY_CHAR_CAP", 4000)

        self.assertEqual(result, 4000)

    def test_context_char_cap_is_bounded(self):
        with patch.dict(os.environ, {"PA_AGENTS_CHAR_CAP": "50000"}, clear=True):
            high_result = load_context_char_cap("PA_AGENTS_CHAR_CAP", 4000)

        with patch.dict(os.environ, {"PA_CONTEXT_SECTION_CHAR_CAP": "-1"}, clear=True):
            low_result = load_context_char_cap("PA_CONTEXT_SECTION_CHAR_CAP", 4000)

        self.assertEqual(high_result, 20000)
        self.assertEqual(low_result, 0)


if __name__ == "__main__":
    unittest.main()
