# EV Battery Health and Charging Intelligence Platform

An end-to-end data engineering portfolio project for connected electric vehicle telemetry. The platform uses a medallion architecture to turn raw battery and charging events into analytics-ready data products for battery health, charging behavior, warranty risk, and fleet operations.

## Why This Project

German automotive teams increasingly need data engineers who can work across software-defined vehicles, EV battery data, connected fleet telemetry, data quality, and auditable data products. This project demonstrates those skills through a realistic, reproducible platform.

## Architecture

- **Bronze**: raw JSONL telemetry events from simulated vehicles
- **Silver**: normalized, deduplicated, schema-checked battery and charging sessions
- **Gold**: battery health KPIs, charging intelligence, thermal risk, and warranty signals

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

