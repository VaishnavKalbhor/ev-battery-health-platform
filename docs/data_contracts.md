# Data Contracts

This project treats the silver layer as the first trusted contract boundary. Raw bronze events may contain duplicates, invalid sensor values, or malformed records. Silver datasets must be typed, deduplicated, and valid for downstream analytics.

## Bronze Event

Raw telemetry arrives as JSON Lines.

| Field | Description |
| --- | --- |
| `event_id` | Unique event identifier generated from vehicle and timestamp |
| `timestamp` | Event timestamp in ISO 8601 format |
| `vehicle_id` | Vehicle identifier |
| `pack_id` | Battery pack identifier |
| `model` | Vehicle model category |
| `region` | German region code |
| `soc_pct` | State of charge percentage |
| `soh_pct` | State of health percentage |
| `battery_temp_c` | Battery pack temperature |
| `charger_power_kw` | Charging power when plugged in |
| `energy_delta_kwh` | Energy added or consumed during the interval |
| `is_charging` | Charging state flag |

## Silver Battery Events

Silver events preserve the core bronze fields and add:

| Field | Description |
| --- | --- |
| `event_date` | Date partition derived from timestamp |
| `usable_battery_kwh` | Battery capacity inferred from model |
| `thermal_state` | Normal, elevated, critical, or cold stress |
| `charging_type` | AC, DC standard, DC fast, or not charging |

## Gold Data Products

| Dataset | Purpose |
| --- | --- |
| `battery_health_summary.csv` | One row per vehicle with SOH trend, cycles, odometer, and session count |
| `charging_intelligence.csv` | Regional charging behavior and DC fast-charging share |
| `thermal_risk_events.csv` | Events with elevated or critical battery temperature |
| `warranty_risk_scores.csv` | Vehicle-level warranty risk score and risk band |

