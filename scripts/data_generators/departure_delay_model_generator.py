import os
import random

import numpy as np
import pandas as pd
from tqdm import tqdm

from scripts.data_generators.read_airports import read_airports_csv
from service.dal.container import s3_for_models


def _choose_aircraft_type():
    return random.choice(["A320", "A321", "B737"])  # nosec B311


def _choose_gate():
    return f"{random.choice('ABCDEFGH')}{random.randint(1,45)}"  # nosec B311


def generate_departure_delay_scenario(scenario_id):
    """Generate a single departure scenario with coherent boarding and ground movements.

    The scenario models these high-level phases (in order):
      - gate_open
      - boarding_start -> (boarding minutes) -> boarding_complete
      - gate_close
      - pushback
      - waiting_for_taxi_clearance (short hold)
      - taxiing (several minutes)
      - waiting_for_takeoff_clearance (short hold)
      - takeoff (terminal state)

    Boarding and taxiing take a random, realistic amount of time and the events are produced
    as one-minute-granularity rows so users can analyse minute-by-minute progression.
    """

    # initial environmental conditions (reasonable for European airports)
    temperature = np.random.normal(12.0, 5.0)
    wind_speed = max(0.0, np.random.normal(8.0, 5.0))
    precipitation = 0.0 if np.random.rand() < 0.75 else np.random.exponential(0.3)
    visibility = float(np.clip(np.random.normal(12.0, 2.0), 0.1, 20.0))

    passenger_load = float(np.clip(np.random.normal(0.85, 0.12), 0.1, 1.0))
    aircraft = _choose_aircraft_type()
    gate = _choose_gate()

    rows = []
    event_counter = 0
    timestamp_seconds = 0

    def append(event_name, duration_minutes=1):
        nonlocal event_counter, timestamp_seconds, rows, temperature, wind_speed, precipitation, visibility
        for _ in range(duration_minutes):
            # small random walk for weather each minute
            temperature += np.random.normal(0.0, 0.2)
            temperature = float(np.clip(temperature, -30.0, 45.0))

            wind_speed += np.random.normal(0.0, 0.5)
            wind_speed = float(np.clip(wind_speed, 0.0, 250.0))

            # precipitation may start or intensify slowly
            if precipitation > 0.05:
                precipitation += np.random.exponential(0.2) * 0.3
            else:
                if np.random.rand() < 0.02:
                    precipitation = np.random.exponential(0.4)
                else:
                    precipitation = max(0.0, precipitation + np.random.normal(0.0, 0.01))
            precipitation = float(np.clip(precipitation, 0.0, 200.0))

            # visibility affected by precipitation/fog
            fog_factor = 0.0
            if np.random.rand() < 0.005:
                fog_factor = np.random.uniform(0.5, 2.0)
            visibility += np.random.normal(0.0, 0.1) - precipitation * 0.06 - fog_factor
            visibility = float(np.clip(visibility, 0.05, 20.0))

            # choose weather event
            if precipitation > 15 or (precipitation > 5 and np.random.rand() < 0.25):
                weather_event = "thunderstorm" if np.random.rand() < 0.18 else "rain"
            elif precipitation > 1.2:
                weather_event = "rain"
            elif visibility < 1.0:
                weather_event = "fog"
            elif temperature <= 0.0 and precipitation > 0.1:
                weather_event = "snow"
            else:
                weather_event = "clear"

            # runway/ground condition heuristic
            if weather_event in ("thunderstorm", "snow") or precipitation > 3.0:
                runway_condition = "wet"
            else:
                runway_condition = "dry"

            row = {
                "scenario_id": int(scenario_id),
                "event_id": int(event_counter),
                "event_timestamp_in_seconds": int(timestamp_seconds),
                "temperature_celsius": round(float(temperature), 2),
                "wind_speed_kmh": round(float(wind_speed), 2),
                "precipitation_mm": round(float(precipitation), 3),
                "visibility_km": round(float(visibility), 2),
                "weather_event": weather_event,
                "runway_condition": runway_condition,
                "aircraft_type": aircraft,
                "boarding_gate": gate,
                "passenger_load_percent": round(passenger_load * 100.0, 1),
                "air_traffic_event": event_name,
                "data_value_1": int(np.random.randint(1e5, 1e9)),
                "data_value_2": int(np.random.randint(1e5, 1e9)),
                "data_value_3": int(np.random.randint(1e5, 1e9)),
                "data_value_4": int(np.random.randint(1e5, 1e9)),
            }

            for additional in range(5):
                row[f"data_value_{additional}"] = int(np.random.randint(1e4, 1e10))

            rows.append(row)
            event_counter += 1
            timestamp_seconds += 60  # advance one minute per row

    # Phase 1: gate opens (short)
    append("gate_open", duration_minutes=1)

    boarding_minutes = int(np.clip(int(np.random.exponential(8)) + 10, 50, 70))

    # small chance of delayed boarding or extended boarding due to late arrival / problems
    boarding_issue = None
    r = np.random.rand()
    if r < 0.05:
        boarding_issue = "delayed_boarding"
        extra_minutes = int(np.random.randint(5, 25))
        boarding_minutes += extra_minutes
    elif r < 0.15:
        boarding_issue = "security_hold"
        extra_minutes = int(np.random.randint(2, 15))
        boarding_minutes += extra_minutes

    append("boarding_start", duration_minutes=1)
    # core boarding minutes
    append("boarding", duration_minutes=boarding_minutes)

    if boarding_issue:
        # represent the issue as a few dedicated minutes labelled as the issue
        append(boarding_issue, duration_minutes=int(np.clip(int(np.random.randint(1, 6)), 1, 10)))

    append("boarding_complete", duration_minutes=1)

    # Phase: gate close and pushback
    append("gate_close", duration_minutes=1)
    append("pushback", duration_minutes=1)

    # ground control holds: waiting for taxi clearance (0-5 min), taxiing (3-20 min)
    waiting_for_taxi = int(np.random.choice([0, 0, 1, 1, 2, 3, 5]))
    append("waiting_for_taxi_clearance", duration_minutes=max(1, waiting_for_taxi))

    taxi_minutes = int(np.clip(int(np.random.normal(7, 4)), 5, 35))
    # if runway is wet or snow, taxi can take longer
    if precipitation > 2.5 or visibility < 2.0:
        taxi_minutes += int(np.random.randint(0, 6))

    append("taxiing", duration_minutes=taxi_minutes)

    waiting_for_takeoff = int(np.clip(int(np.random.exponential(1.5)), 0, 8))
    append("waiting_for_takeoff_clearance", duration_minutes=max(1, waiting_for_takeoff))

    append("takeoff", duration_minutes=1)

    # Infer a simple label for flight outcome/delay
    # e.g., significant tailwind might be beneficial, severe weather may delay takeoff
    return pd.DataFrame(rows)


def generate_departure_delay_model(airport_code, num_scenarios=1000):
    """Generate many departure scenarios and concatenate them into a single DataFrame."""

    all_frames = []
    for scenario_id in tqdm(range(int(num_scenarios))):
        df = generate_departure_delay_scenario(scenario_id)
        all_frames.append(df)

    if len(all_frames) == 0:
        return pd.DataFrame(
            columns=[
                "scenario_id",
                "event_id",
                "event_timestamp_in_seconds",
                "temperature_celsius",
                "wind_speed_kmh",
                "precipitation_mm",
                "visibility_km",
                "weather_event",
                "runway_condition",
                "aircraft_type",
                "boarding_gate",
                "passenger_load_percent",
                "air_traffic_event",
                "data_value_1",
                "data_value_2",
                "data_value_3",
                "data_value_4",
            ]
        )

    result = pd.concat(all_frames, ignore_index=True)
    return result


def save_model_to_parquet(df, airport_code, file_path):
    os.makedirs(file_path, exist_ok=True)
    full_path = os.path.join(file_path, f"{airport_code}.parquet")
    df.to_parquet(full_path, index=False)


def main():
    model_id = 4
    airports = read_airports_csv("./data/airports.csv")
    os.makedirs(f"./data/departure_delay_models/{model_id}", exist_ok=True)
    for airport in airports:
        model = generate_departure_delay_model(airport.iata, num_scenarios=50000)
        save_model_to_parquet(model, airport.iata, f"./data/departure_delay_models/{model_id}")
        print(f"Saved departure model locally for {airport.iata}, uploading to S3...")
        # Save model to S3
        s3_for_models(model_id).model_data_access.store_departure_model(model, airport.iata)
        print(f"Saved departure model for {airport.iata}")


if __name__ == "__main__":
    main()
