import json
import unittest
import urllib.error
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from personal_assistant.morning_weather import fetch_weather_summary


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def read(self):
        return self.payload


class MorningWeatherTests(unittest.TestCase):
    def test_blank_location_returns_unavailable_without_api_call(self):
        with patch("personal_assistant.morning_weather.urllib.request.urlopen") as urlopen:
            result = fetch_weather_summary("  ", timeout_seconds=7)

        self.assertEqual(result.name, "weather")
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.exit_code, 0)
        urlopen.assert_not_called()

    def test_successful_weather_summary_uses_geocoding_and_forecast(self):
        urls = []
        timeouts = []

        def fake_urlopen(url, timeout):
            urls.append(url)
            timeouts.append(timeout)
            if "geocoding-api" in url:
                return FakeResponse(
                    {
                        "results": [
                            {
                                "name": "Folkestone",
                                "admin1": "England",
                                "country": "United Kingdom",
                                "latitude": 51.0817,
                                "longitude": 1.1695,
                                "timezone": "Europe/London",
                            }
                        ]
                    }
                )
            return FakeResponse(_forecast_payload())

        with patch("personal_assistant.morning_weather.urllib.request.urlopen", fake_urlopen):
            result = fetch_weather_summary("Folkestone, UK", timeout_seconds=7)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.summary,
            "- Whole Day: 13 C to 22 C, precipitation 1.4 mm with 40% max chance, "
            "max wind 20 km/h gusting 35 km/h.\n"
            "- Light: sunrise 05:00, sunset 21:10, UV max 6.",
        )
        self.assertNotIn("Open-Meteo weather for", result.summary)
        self.assertNotIn("Source:", result.summary)
        self.assertNotIn("Current:", result.summary)
        self.assertNotIn("Morning (06-12):", result.summary)
        self.assertNotIn("Afternoon (12-18):", result.summary)
        self.assertNotIn("Evening (18-24):", result.summary)
        self.assertNotIn("Overnight (00-06):", result.summary)
        self.assertIn("sunrise 05:00", result.summary)
        self.assertEqual(timeouts, [7, 7])

        geocode_query = parse_qs(urlparse(urls[0]).query)
        self.assertEqual(geocode_query["name"], ["Folkestone"])
        self.assertEqual(geocode_query["countryCode"], ["GB"])

        forecast_query = parse_qs(urlparse(urls[1]).query)
        self.assertEqual(forecast_query["timezone"], ["Europe/London"])
        self.assertEqual(forecast_query["forecast_days"], ["1"])
        self.assertIn("temperature_2m_max", forecast_query["daily"][0])
        self.assertNotIn("current", forecast_query)
        self.assertNotIn("hourly", forecast_query)

    def test_missing_geocode_result_returns_failed(self):
        def fake_urlopen(_url, timeout):
            return FakeResponse({"results": []})

        with patch("personal_assistant.morning_weather.urllib.request.urlopen", fake_urlopen):
            result = fetch_weather_summary("Nowhere", timeout_seconds=7)

        self.assertEqual(result.status, "failed")
        self.assertIn("could not resolve", result.summary)

    def test_uk_suffix_without_comma_adds_country_code(self):
        urls = []

        def fake_urlopen(url, timeout):
            urls.append(url)
            return FakeResponse({"results": []})

        with patch("personal_assistant.morning_weather.urllib.request.urlopen", fake_urlopen):
            fetch_weather_summary("Folkestone UK", timeout_seconds=7)

        geocode_query = parse_qs(urlparse(urls[0]).query)
        self.assertEqual(geocode_query["name"], ["Folkestone"])
        self.assertEqual(geocode_query["countryCode"], ["GB"])

    def test_url_error_returns_failed(self):
        def fake_urlopen(_url, timeout):
            raise urllib.error.URLError("Temporary failure in name resolution")

        with patch("personal_assistant.morning_weather.urllib.request.urlopen", fake_urlopen):
            result = fetch_weather_summary("Folkestone, UK", timeout_seconds=7)

        self.assertEqual(result.status, "failed")
        self.assertIn("Temporary failure", result.summary)

    def test_invalid_json_returns_failed(self):
        class InvalidJsonResponse:
            def __enter__(self):
                return self

            def __exit__(self, _exc_type, _exc, _traceback):
                return False

            def read(self):
                return b"not-json"

        with patch(
            "personal_assistant.morning_weather.urllib.request.urlopen",
            return_value=InvalidJsonResponse(),
        ):
            result = fetch_weather_summary("Folkestone, UK", timeout_seconds=7)

        self.assertEqual(result.status, "failed")
        self.assertIn("not valid JSON", result.summary)


def _forecast_payload():
    return {
        "daily": {
            "temperature_2m_max": [22],
            "temperature_2m_min": [13],
            "precipitation_sum": [1.4],
            "precipitation_probability_max": [40],
            "wind_speed_10m_max": [20],
            "wind_gusts_10m_max": [35],
            "sunrise": ["2026-07-09T05:00"],
            "sunset": ["2026-07-09T21:10"],
            "uv_index_max": [6],
        },
    }


if __name__ == "__main__":
    unittest.main()
