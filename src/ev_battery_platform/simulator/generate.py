from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from uuid import uuid5, NAMESPACE_URL


GERMAN_REGIONS = [
    ("DE-BW", 48.7758, 9.1829),
    ("DE-BY", 48.1351, 11.5820),
    ("DE-BE", 52.5200, 13.4050),
    ("DE-HH", 53.5511, 9.9937),
    ("DE-NI", 52.3759, 9.7320),
    ("DE-NW", 51.2277, 6.7735),
    ("DE-SN", 51.0504, 13.7373),
]

VEHICLE_MODELS = [
    ("compact_ev", 58.0),
    ("premium_sedan_ev", 89.0),
    ("suv_ev", 104.0),
    ("delivery_van_ev", 78.0),
]


@dataclass(frozen=True)
class GenerationConfig:
    seed: int = 42
    fleet_size: int = 50
    days: int = 14
    events_per_vehicle_per_day: int = 72
    start_date: datetime = datetime(2026, 1, 1, tzinfo=timezone.utc)
    output_path: Path = Path("data/bronze/ev_telemetry_raw.jsonl")

    @property
    def total_events(self) -> int:
        return self.fleet_size * self.days * self.events_per_vehicle_per_day


def load_config(path: Path) -> GenerationConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return GenerationConfig(
        seed=int(payload.get("seed", 42)),
        fleet_size=int(payload.get("fleet_size", 50)),
        days=int(payload.get("days", 14)),
        events_per_vehicle_per_day=int(payload.get("events_per_vehicle_per_day", 72)),
        start_date=datetime.fromisoformat(payload.get("start_date")).astimezone(timezone.utc),
        output_path=Path(payload.get("output_path", "data/bronze/ev_telemetry_raw.jsonl")),
    )


def generate_telemetry(config: GenerationConfig) -> int:
    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = _iter_events(config)

    with config.output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, separators=(",", ":"), sort_keys=True))
            handle.write("\n")

    return config.total_events


def _iter_events(config: GenerationConfig) -> Iterable[dict[str, object]]:
    rng = random.Random(config.seed)
    step_minutes = (24 * 60) // config.events_per_vehicle_per_day

    for vehicle_idx in range(config.fleet_size):
        region, base_lat, base_lon = rng.choice(GERMAN_REGIONS)
        model, usable_battery_kwh = rng.choice(VEHICLE_MODELS)
        vehicle_id = f"EV-{vehicle_idx + 1:05d}"
        odometer_km = rng.uniform(2_000, 95_000)
        state_of_health_pct = rng.uniform(86.0, 99.5)
        soc_pct = rng.uniform(35.0, 95.0)
        firmware_version = rng.choice(["bms-2025.12", "bms-2026.01", "bms-2026.02"])
        pack_id = f"PACK-{rng.randrange(100000, 999999)}"

        for event_idx in range(config.days * config.events_per_vehicle_per_day):
            timestamp = config.start_date + timedelta(minutes=step_minutes * event_idx)
            hour = timestamp.hour + timestamp.minute / 60
            is_commute_window = 6.5 <= hour <= 9.5 or 16.0 <= hour <= 19.5
            is_charging = soc_pct < 25 or (rng.random() < 0.12 and not is_commute_window)
            ambient_temp_c = _ambient_temperature(timestamp, region, rng)

            if is_charging:
                charger_power_kw = rng.choice([11.0, 22.0, 50.0, 150.0, 250.0])
                energy_delta_kwh = min(
                    usable_battery_kwh * (100 - soc_pct) / 100,
                    charger_power_kw * step_minutes / 60 * rng.uniform(0.65, 0.95),
                )
                speed_kmh = 0.0
                soc_pct = min(100.0, soc_pct + (energy_delta_kwh / usable_battery_kwh) * 100)
            else:
                charger_power_kw = 0.0
                speed_kmh = _vehicle_speed(hour, is_commute_window, rng)
                distance_delta_km = speed_kmh * step_minutes / 60
                consumption_kwh_per_100km = rng.uniform(15.0, 27.0) * (1.0 + max(0, 5 - ambient_temp_c) * 0.015)
                energy_delta_kwh = -distance_delta_km * consumption_kwh_per_100km / 100
                odometer_km += distance_delta_km
                soc_pct = max(3.0, soc_pct + (energy_delta_kwh / usable_battery_kwh) * 100)

            state_of_health_pct = max(
                65.0,
                state_of_health_pct - abs(energy_delta_kwh) * rng.uniform(0.000004, 0.000012),
            )
            battery_temp_c = ambient_temp_c + abs(charger_power_kw) * 0.035 + speed_kmh * 0.025 + rng.gauss(0, 1.7)
            voltage_v = _pack_voltage(soc_pct, usable_battery_kwh, rng)
            current_a = (charger_power_kw * 1000 / voltage_v) if is_charging else -(abs(energy_delta_kwh) * 60 / step_minutes * 1000 / voltage_v)
            lat = base_lat + rng.uniform(-0.18, 0.18)
            lon = base_lon + rng.uniform(-0.25, 0.25)
            event_id = str(uuid5(NAMESPACE_URL, f"{vehicle_id}:{timestamp.isoformat()}"))

            row = {
                "event_id": event_id,
                "timestamp": timestamp.isoformat(),
                "vehicle_id": vehicle_id,
                "pack_id": pack_id,
                "model": model,
                "region": region,
                "firmware_version": firmware_version,
                "odometer_km": round(odometer_km, 2),
                "latitude": round(lat, 6),
                "longitude": round(lon, 6),
                "speed_kmh": round(speed_kmh, 2),
                "soc_pct": round(soc_pct, 2),
                "soh_pct": round(state_of_health_pct, 3),
                "battery_temp_c": round(battery_temp_c, 2),
                "ambient_temp_c": round(ambient_temp_c, 2),
                "voltage_v": round(voltage_v, 2),
                "current_a": round(current_a, 2),
                "charger_power_kw": round(charger_power_kw, 2),
                "energy_delta_kwh": round(energy_delta_kwh, 4),
                "is_charging": is_charging,
            }

            anomaly_roll = rng.random()
            if anomaly_roll < 0.002:
                row["soc_pct"] = round(rng.uniform(101.0, 118.0), 2)
            elif anomaly_roll < 0.004:
                row["battery_temp_c"] = round(rng.uniform(65.0, 88.0), 2)
            elif anomaly_roll < 0.006:
                row["event_id"] = f"DUPLICATE-{vehicle_id}-{event_idx // 8}"

            yield row


def _ambient_temperature(timestamp: datetime, region: str, rng: random.Random) -> float:
    seasonal = 7.0 * math.sin((timestamp.timetuple().tm_yday - 80) / 365 * 2 * math.pi)
    daily = 4.0 * math.sin((timestamp.hour - 7) / 24 * 2 * math.pi)
    north_adjustment = -2.0 if region in {"DE-HH", "DE-NI"} else 0.0
    south_adjustment = 1.0 if region in {"DE-BW", "DE-BY"} else 0.0
    return 9.0 + seasonal + daily + north_adjustment + south_adjustment + rng.gauss(0, 1.2)


def _vehicle_speed(hour: float, is_commute_window: bool, rng: random.Random) -> float:
    if rng.random() < 0.45 and not is_commute_window:
        return 0.0
    if is_commute_window:
        return max(0.0, rng.gauss(43, 18))
    return max(0.0, rng.gauss(65, 32))


def _pack_voltage(soc_pct: float, usable_battery_kwh: float, rng: random.Random) -> float:
    nominal_voltage = 390 if usable_battery_kwh < 80 else 705
    return nominal_voltage * (0.86 + soc_pct / 100 * 0.22) + rng.gauss(0, 3.5)

