# Morning Rundown Weather

`pa morning-rundown` fetches optional weather directly from Open-Meteo instead
of launching a Codex weather search agent. Configure the location with
`PA_RUNDOWN_WEATHER_LOCATION`, or put the first non-comment location line in:

```text
$HOME/.config/personal-assistant/weather-location
```

The generated journal keeps weather compact. A successful lookup contributes
only two child lines under `Weather`:

```markdown
  - Weather
    - Whole Day: ...
    - Light: ...
```

The forecast request uses daily Open-Meteo fields only. It does not request
`current` or `hourly` data, and it no longer writes Current, Overnight,
Morning, Afternoon, Evening, or Source lines into the journal.

Weather failures are degraded, not blocking, when the reviewer succeeds. The
journal still records the weather source status and the command exits nonzero.
