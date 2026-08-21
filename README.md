# EV Battery Health and Charging Intelligence Platform

An end-to-end data engineering portfolio project for connected electric vehicle telemetry. The platform uses a medallion architecture to turn raw battery and charging events into analytics-ready data products for battery health, charging behavior, warranty risk, and fleet operations.

## Why This Project

German automotive teams increasingly need data engineers who can work across software-defined vehicles, EV battery data, connected fleet telemetry, data quality, and auditable data products. This project demonstrates those skills through a realistic, reproducible platform.

## Architecture

- **Bronze**: raw JSONL telemetry events from simulated vehicles
- **Silver**: normalized, deduplicated, schema-checked battery and charging sessions
- **Gold**: battery health KPIs, charging intelligence, thermal risk, and warranty signals

```text
vehicle telemetry generator
        |
        v
data/bronze/ev_telemetry_raw.jsonl
        |
        v
data/silver/battery_events.csv
data/silver/charging_sessions.csv
data/silver/rejected_events.csv
        |
        v
data/gold/battery_health_summary.csv
data/gold/charging_intelligence.csv
data/gold/thermal_risk_events.csv
data/gold/warranty_risk_scores.csv
```

## Project Layout

```text
config/                         pipeline configuration
data/bronze/                    raw telemetry landing zone
data/silver/                    cleaned and normalized datasets
data/gold/                      analytics-ready data products
docs/                           architecture and portfolio notes
src/ev_battery_platform/        application package
tests/                          regression tests
```

## Roadmap

- Synthetic telemetry generator for fleet-scale EV events
- Medallion pipeline from raw events to gold data products
- Data quality checks for schema, ranges, duplicates, and null handling
- Battery state-of-health and charging behavior analytics
- Dashboard-ready CSV outputs and portfolio documentation

## Quick Start

```powershell
python -m pip install -e .
python -m ev_battery_platform generate --config config/fleet_sample.json
python -m ev_battery_platform run
python -m ev_battery_platform quality
python -m ev_battery_platform dashboard
python -m unittest discover -s tests
```

## Example Outputs

After running the sample configuration, the platform creates:

- 50,400 raw bronze telemetry events
- Silver battery event and charging session datasets
- Gold data products for fleet health, regional charging behavior, thermal risk, and warranty scoring
- A Markdown quality report at `reports/data_quality.md`
- A self-contained HTML dashboard at `reports/dashboard.html`
- An executive Markdown report at `reports/executive_summary.md`

## Portfolio Talking Points

- Designed a medallion architecture for connected EV battery telemetry.
- Built a deterministic fleet simulator to generate reproducible raw events.
- Modeled realistic data issues, including duplicate events and out-of-range sensor values.
- Implemented silver normalization with domain ranges, event deduplication, and rejected-record capture.
- Produced gold data products for battery health, charging intelligence, thermal exposure, and warranty risk.
- Added automated data quality checks and CI-backed regression tests.
- Generated dashboard and executive report outputs from trusted gold datasets.

## Production Mapping

The local implementation is dependency-light by design. In a production automotive environment, the same layers can be mapped to:

- Kafka or MQTT for telemetry ingestion
- Object storage for the bronze landing zone
- Spark Structured Streaming for scalable transformations
- Delta Lake or Apache Iceberg for governed medallion tables
- dbt for SQL transformations and documentation
- Great Expectations or Soda for data quality checks
- Superset, Grafana, Power BI, or Tableau for fleet dashboards
