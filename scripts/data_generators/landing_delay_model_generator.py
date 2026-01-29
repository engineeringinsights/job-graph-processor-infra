import os

import numpy as np
import pandas as pd
from tqdm import tqdm

from scripts.data_generators.read_airports import read_airports_csv
from service.dal.container import s3_for_models


def generate_landing_delay_scenario(scenario_id, max_events=120):
    """Generate a single landing scenario with consistent, gradual weather changes and
    coherent air traffic events. Returns a pandas DataFrame for the scenario."""

    # decide scenario length using a mixture to bias toward short holds but allow long ones
    r = np.random.rand()
    if r < 0.3:
        n_events = np.random.randint(1, 11)  # optimistic/short
    elif r < 0.9:
        n_events = np.random.randint(11, 31)  # average
    else:
        n_events = np.random.randint(31, max_events + 1)  # severe

    # initial weather conditions (European ranges)
    temperature = np.random.normal(10.0, 6.0)  # degrees Celsius
    wind_speed = max(0.0, np.random.normal(10.0, 6.0))  # km/h
    precipitation = 0.0 if np.random.rand() < 0.7 else np.random.exponential(0.4)  # mm per minute
    visibility = float(np.clip(np.random.normal(10.0, 2.0), 0.1, 20.0))  # km

    rows = []

    for event_id in range(n_events):
        # small, bounded random walk for continuous variables
        temperature += np.random.normal(0.0, 0.3)
        temperature = float(np.clip(temperature, -20.0, 40.0))

        wind_speed += np.random.normal(0.0, 0.8)
        wind_speed = float(np.clip(wind_speed, 0.0, 200.0))

        # precipitation evolves: if already raining it tends to continue or grow slightly,
        # otherwise it can start with a small probability
        if precipitation > 0.1:
            precipitation += np.random.exponential(0.3) * 0.5
        else:
            if np.random.rand() < 0.05:
                precipitation = np.random.exponential(0.4)
            else:
                # small chance of flurries / drizzle
                precipitation = max(0.0, precipitation + np.random.normal(0.0, 0.02))

        precipitation = float(np.clip(precipitation, 0.0, 100.0))

        # visibility depends on precipitation and chance of fog
        fog_factor = 0.0
        if np.random.rand() < 0.01:
            fog_factor = np.random.uniform(0.5, 3.0)
        visibility += np.random.normal(0.0, 0.2) - precipitation * 0.08 - fog_factor
        visibility = float(np.clip(visibility, 0.05, 20.0))

        # determine dominant weather_event
        if precipitation > 15 or (precipitation > 5 and np.random.rand() < 0.3):
            weather_event = "thunderstorm" if np.random.rand() < 0.25 else "rain"
        elif precipitation > 1.0:
            weather_event = "rain"
        elif visibility < 1.0:
            weather_event = "fog"
        elif temperature <= 0.0 and precipitation > 0.1:
            weather_event = "snow"
        else:
            weather_event = "clear"

        # air traffic event: keep holds until last event which should be a terminal state
        if n_events == 1:
            air_traffic_event = "landing_approved"
        else:
            if event_id < n_events - 1:
                # while holding: prefer weather holds if conditions are bad
                if weather_event in ("thunderstorm", "snow", "fog") or precipitation > 3.0:
                    air_traffic_event = "hold_for_weather"
                else:
                    # could be hold for traffic or brief sequencing delays
                    air_traffic_event = "hold_for_traffic" if np.random.rand() < 0.6 else "hold_for_weather"
            else:
                air_traffic_event = "landing_approved"

        row = {
            "scenario_id": int(scenario_id),
            "event_id": int(event_id),
            "event_timestamp_in_seconds": int(event_id * 60),
            "temperature_celsius": round(float(temperature), 2),
            "wind_speed_kmh": round(float(wind_speed), 2),
            "precipitation_mm": round(float(precipitation), 3),
            "visibility_km": round(float(visibility), 2),
            "weather_event": weather_event,
            "air_traffic_event": air_traffic_event,
        }
        for additional in range(20):
            row[f"data_value_{additional}"] = int(np.random.randint(1e4, 1e10))

        rows.append(row)

    return pd.DataFrame(rows)


def generate_landing_delay_model(airport_code, num_scenarios=1000):
    """Generate a Monte-Carlo dataset of landing scenarios for an airport.

    Each scenario contains between 1 and 120 events spaced one minute apart. The function
    returns a pandas DataFrame concatenating all generated scenario event rows. Columns follow
    the schema documented in the original docstring above.

    Parameters:
    - airport_code: str (reserved for future use)
    - num_scenarios: how many scenarios to generate (default 10_000)

    Returns:
    - pandas.DataFrame with rows = total events across all scenarios
    """

    all_frames = []
    for scenario_id in tqdm(range(int(num_scenarios))):
        df = generate_landing_delay_scenario(scenario_id)
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
                "air_traffic_event",
                "data_value_1",
                "data_value_2",
                "data_value_3",
                "data_value_4",
            ]
        )

    result = pd.concat(all_frames, ignore_index=True)
    return result


def save_model_to_parquet(weather_df, airport_code, file_path):
    full_path = f"{file_path}/{airport_code}.parquet"
    weather_df.to_parquet(full_path, index=False)


def main():
    model_id = 4
    airports = read_airports_csv("./data/airports.csv")
    os.makedirs(f"./data/landing_delay_models/{model_id}", exist_ok=True)
    for airport in airports:
        model = generate_landing_delay_model(airport.iata, num_scenarios=50000)
        save_model_to_parquet(model, airport.iata, f"./data/landing_delay_models/{model_id}")
        print(f"Saved landing model locally for {airport.iata}, uploading to S3...")
        # Save model to S3
        s3_for_models(model_id).model_data_access.store_landing_model(model, airport.iata)
        print(f"Saved landing model for {airport.iata}")


if __name__ == "__main__":
    main()
