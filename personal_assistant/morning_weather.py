import json
import urllib.error
import urllib.parse
import urllib.request

from personal_assistant.morning_agents import AgentResult


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

DAILY_FIELDS = (
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "precipitation_probability_max",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "sunrise",
    "sunset",
    "uv_index_max",
)


class WeatherLookupError(Exception):
    pass


def fetch_weather_summary(location, timeout_seconds):
    location = str(location or "").strip()
    if not location:
        return AgentResult(
            "weather",
            "unavailable",
            "No weather location is configured; weather was not fetched.",
            0,
        )

    try:
        place = _geocode_location(location, timeout_seconds)
        if place is None:
            return AgentResult(
                "weather",
                "failed",
                f"Open-Meteo could not resolve weather location: {location}",
                1,
            )
        forecast = _fetch_forecast(place, timeout_seconds)
        summary = _format_summary(forecast)
    except WeatherLookupError as error:
        return AgentResult("weather", "failed", str(error), 1)

    return AgentResult("weather", "ok", summary, 0)


def _geocode_location(location, timeout_seconds):
    payload = _read_json(_geocoding_url(location), timeout_seconds)
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        return None

    place = results[0]
    if "latitude" not in place or "longitude" not in place:
        raise WeatherLookupError("Open-Meteo geocoding response was missing coordinates.")
    return place


def _fetch_forecast(place, timeout_seconds):
    return _read_json(_forecast_url(place), timeout_seconds)


def _read_json(url, timeout_seconds):
    try:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            data = response.read()
    except TimeoutError:
        raise WeatherLookupError("Open-Meteo weather lookup timed out.")
    except urllib.error.HTTPError as error:
        raise WeatherLookupError(f"Open-Meteo weather lookup failed with HTTP {error.code}.")
    except urllib.error.URLError as error:
        raise WeatherLookupError(f"Open-Meteo weather lookup failed: {error.reason}")
    except OSError as error:
        raise WeatherLookupError(f"Open-Meteo weather lookup failed: {error}")

    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WeatherLookupError(f"Open-Meteo weather response was not valid JSON: {error}")


def _geocoding_url(location):
    params = {
        "name": _search_name(location),
        "count": "1",
        "language": "en",
        "format": "json",
    }
    country_code = _country_code_hint(location)
    if country_code:
        params["countryCode"] = country_code
    return GEOCODING_URL + "?" + urllib.parse.urlencode(params)


def _forecast_url(place):
    params = {
        "latitude": str(place["latitude"]),
        "longitude": str(place["longitude"]),
        "daily": ",".join(DAILY_FIELDS),
        "timezone": place.get("timezone") or "auto",
        "forecast_days": "1",
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
    }
    return FORECAST_URL + "?" + urllib.parse.urlencode(params)


def _search_name(location):
    search_name, _country_code = _split_country_suffix(location)
    return search_name


def _country_code_hint(location):
    _search_name, country_code = _split_country_suffix(location)
    return country_code


def _split_country_suffix(location):
    text = str(location).strip()
    parts = [part.strip() for part in str(location).split(",") if part.strip()]
    if len(parts) > 1 and _normalise_country(parts[-1]) in ("uk", "gb", "united kingdom", "great britain"):
        return ", ".join(parts[:-1]), "GB"

    normalised = _normalise_country(text)
    for suffix in (" united kingdom", " great britain", " uk", " gb"):
        if normalised.endswith(suffix):
            return text[: -len(suffix)].strip(" ,"), "GB"
    return text, ""


def _normalise_country(value):
    return str(value).strip().lower().replace(".", "")


def _format_summary(forecast):
    daily = forecast.get("daily")
    if not isinstance(daily, dict):
        raise WeatherLookupError("Open-Meteo forecast response was missing weather data.")

    _require_daily(daily)

    lines = [
        (
            "- Whole Day: "
            f"{_format_value(_daily_value(daily, 'temperature_2m_min'), ' C')} to "
            f"{_format_value(_daily_value(daily, 'temperature_2m_max'), ' C')}, "
            f"precipitation {_format_value(_daily_value(daily, 'precipitation_sum'), ' mm')} "
            f"with {_format_value(_daily_value(daily, 'precipitation_probability_max'), '%')} max chance, "
            f"max wind {_format_value(_daily_value(daily, 'wind_speed_10m_max'), ' km/h')} "
            f"gusting {_format_value(_daily_value(daily, 'wind_gusts_10m_max'), ' km/h')}."
        ),
        (
            "- Light: "
            f"sunrise {_format_time(_daily_value(daily, 'sunrise'))}, "
            f"sunset {_format_time(_daily_value(daily, 'sunset'))}, "
            f"UV max {_format_value(_daily_value(daily, 'uv_index_max'), '')}."
        ),
    ]
    return "\n".join(lines)


def _require_daily(daily):
    missing = [field for field in DAILY_FIELDS if _daily_value(daily, field) is None]
    if missing:
        raise WeatherLookupError("Open-Meteo daily weather missing fields: " + ", ".join(missing))


def _daily_value(daily, field):
    values = daily.get(field)
    if isinstance(values, list) and values:
        return values[0]
    return None


def _format_value(value, suffix):
    if value is None:
        return "unknown"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return f"{value}{suffix}"
    if number.is_integer():
        return f"{int(number)}{suffix}"
    return f"{number:.1f}".rstrip("0").rstrip(".") + suffix


def _format_time(value):
    text = str(value or "unknown")
    if "T" in text:
        return text.split("T", 1)[1]
    return text
