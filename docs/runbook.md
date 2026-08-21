# Local Runbook

## Setup

```powershell
python -m pip install -e .
```

## Generate Raw Telemetry

```powershell
python -m ev_battery_platform generate --config config/fleet_sample.json
```

## Run the Medallion Pipeline

```powershell
python -m ev_battery_platform run
```

## Run Quality Checks

```powershell
python -m ev_battery_platform quality
```

## Run Tests

```powershell
python -m unittest discover -s tests
```

## Expected Local Outputs

| Path | Description |
| --- | --- |
| `data/bronze/ev_telemetry_raw.jsonl` | Raw generated telemetry |
| `data/silver/battery_events.csv` | Clean event-level silver table |
| `data/silver/charging_sessions.csv` | Sessionized charging table |
| `data/silver/rejected_events.csv` | Invalid or duplicate bronze records |
| `data/gold/*.csv` | Dashboard-ready analytics products |
| `reports/data_quality.md` | Latest quality report |

