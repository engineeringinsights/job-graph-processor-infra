from datetime import time

import pandas as pd


def model_departure_delays(
    departure_model_df: pd.DataFrame, gate_open_time: time, take_off_time: time
):
    delta_in_minutes = (take_off_time.hour * 60 + take_off_time.minute) - (
        gate_open_time.hour * 60 + gate_open_time.minute
    )

    scenario_durations = (
        departure_model_df.groupby("scenario_id")
        .agg(
            {
                "event_timestamp_in_seconds": "max",
                "data_value_1": "min",
                "data_value_2": "min",
                "data_value_3": "min",
                "data_value_4": "min",
            }
        )
        .reset_index()
    )
    scenario_durations["scenario_duration_in_minutes"] = (
        scenario_durations["event_timestamp_in_seconds"] / 60
    )
    scenario_durations["delay_in_minutes"] = (
        scenario_durations["scenario_duration_in_minutes"] - delta_in_minutes
    )
    return scenario_durations[
        [
            "scenario_id",
            "delay_in_minutes",
            "data_value_1",
            "data_value_2",
            "data_value_3",
            "data_value_4",
        ]
    ]


def model_landing_delays(landing_model_df: pd.DataFrame, landing_time_minutes: int):
    scenario_durations = (
        landing_model_df.groupby("scenario_id")
        .agg(
            {
                "event_timestamp_in_seconds": "max",
                "data_value_1": "min",
                "data_value_2": "min",
                "data_value_3": "min",
                "data_value_4": "min",
            }
        )
        .reset_index()
    )
    scenario_durations["scenario_duration_in_minutes"] = (
        scenario_durations["event_timestamp_in_seconds"] / 60
    )
    scenario_durations["delay_in_minutes"] = (
        scenario_durations["scenario_duration_in_minutes"] - landing_time_minutes
    )
    return scenario_durations[
        [
            "scenario_id",
            "delay_in_minutes",
            "data_value_1",
            "data_value_2",
            "data_value_3",
            "data_value_4",
        ]
    ]


def merge_departure_and_landing_delays(
    departure_delays: pd.DataFrame, landing_delays: pd.DataFrame
) -> pd.DataFrame:
    # Merge both dataframes on scenario_id
    # sum the delays and all data_values
    # output columns: 'scenario_id',  'delay_in_minutes', 'data_value_1', 'data_value_2', 'data_value_3', 'data_value_4'
    merged = pd.merge(
        departure_delays,
        landing_delays,
        on="scenario_id",
        suffixes=("_departure", "_landing"),
    )
    merged["delay_in_minutes"] = (
        merged["delay_in_minutes_departure"] + merged["delay_in_minutes_landing"]
    )
    merged["data_value_1"] = (
        merged["data_value_1_departure"] + merged["data_value_1_landing"]
    )
    merged["data_value_2"] = (
        merged["data_value_2_departure"] + merged["data_value_2_landing"]
    )
    merged["data_value_3"] = (
        merged["data_value_3_departure"] + merged["data_value_3_landing"]
    )
    merged["data_value_4"] = (
        merged["data_value_4_departure"] + merged["data_value_4_landing"]
    )
    return merged[
        [
            "scenario_id",
            "delay_in_minutes",
            "data_value_1",
            "data_value_2",
            "data_value_3",
            "data_value_4",
        ]
    ]


def merge_with_previous_airport_delays(
    previous_delays: pd.DataFrame, current_delays: pd.DataFrame
) -> pd.DataFrame:
    # Merge both dataframes on scenario_id
    # sum the delays and all data_values
    # output columns: 'scenario_id',  'delay_in_minutes', 'data_value_1', 'data_value_2', 'data_value_3', 'data_value_4'
    merged = pd.merge(
        previous_delays,
        current_delays,
        on="scenario_id",
        suffixes=("_previous", "_current"),
    )
    merged["delay_in_minutes"] = (
        merged["delay_in_minutes_previous"] + merged["delay_in_minutes_current"]
    )
    merged["data_value_1"] = (
        merged["data_value_1_previous"] + merged["data_value_1_current"]
    )
    merged["data_value_2"] = (
        merged["data_value_2_previous"] + merged["data_value_2_current"]
    )
    merged["data_value_3"] = (
        merged["data_value_3_previous"] + merged["data_value_3_current"]
    )
    merged["data_value_4"] = (
        merged["data_value_4_previous"] + merged["data_value_4_current"]
    )
    return merged[
        [
            "scenario_id",
            "delay_in_minutes",
            "data_value_1",
            "data_value_2",
            "data_value_3",
            "data_value_4",
        ]
    ]


def calculate_percentiles(merged_delays: pd.DataFrame) -> dict:
    # from merged_delays calculates the 50th, 75th, 90th, 95th and 99th percentiles of delay_in_minutes
    percentiles = [50, 75, 90, 95, 99, 99.5, 99.9]
    results = {}
    for p in percentiles:
        results[f"percentile_{p}"] = merged_delays["delay_in_minutes"].quantile(
            p / 100.0
        )
    return results


def merge_percentiles(percentiles_list: list[tuple[int, dict]]) -> dict:
    merged = {}
    for id, percentiles in percentiles_list:
        merged[id] = percentiles
    return merged
