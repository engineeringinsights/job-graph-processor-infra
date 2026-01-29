import os
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

# Mock environment variables before importing modules that need them
os.environ.setdefault("BUCKET_NAME", "test-bucket")
os.environ.setdefault("TABLE_NAME", "test-table")
os.environ.setdefault("OUTGOING_QUEUE_URL", "test-queue")
os.environ.setdefault("TEST_RUN_ID", "test-run")

from scripts.data_generators.aircraft_daily_sequence_generator import (
    calculate_flight_duration,
    generate_aircraft_daily_sequences,
    try_generate_sequence,
)
from scripts.data_generators.departure_delay_model_generator import (
    generate_departure_delay_model,
    generate_departure_delay_scenario,
)
from scripts.data_generators.departure_delay_model_generator import (
    save_model_to_parquet as save_departure_to_parquet,
)
from scripts.data_generators.landing_delay_model_generator import (
    generate_landing_delay_model,
    generate_landing_delay_scenario,
)
from scripts.data_generators.landing_delay_model_generator import (
    save_model_to_parquet as save_landing_to_parquet,
)
from service.models.aircraft_daily_sequence_dto import DailySequenceDto
from service.models.airport import AirportDto


class TestCalculateFlightDuration:
    def test_calculates_duration_between_two_points(self):
        # Dublin (DUB) to London (LHR) - approximately 450 km
        dublin_lon, dublin_lat = -6.27, 53.35
        london_lon, london_lat = -0.46, 51.47

        duration = calculate_flight_duration(dublin_lon, dublin_lat, london_lon, london_lat, 800.0)

        assert isinstance(duration, timedelta)
        # Should be roughly 30-40 minutes at 800 km/h
        assert 20 <= duration.total_seconds() / 60 <= 60

    def test_same_location_returns_zero_duration(self):
        lon, lat = 10.0, 50.0

        duration = calculate_flight_duration(lon, lat, lon, lat, 800.0)

        assert duration.total_seconds() == 0

    def test_different_speeds_affect_duration(self):
        lon1, lat1 = 0.0, 50.0
        lon2, lat2 = 5.0, 50.0

        duration_fast = calculate_flight_duration(lon1, lat1, lon2, lat2, 1000.0)
        duration_slow = calculate_flight_duration(lon1, lat1, lon2, lat2, 500.0)

        assert duration_slow > duration_fast


class TestTryGenerateSequence:
    @pytest.fixture
    def airports(self):
        return [
            AirportDto(
                id=1,
                iata="DUB",
                name="Dublin",
                city="Dublin",
                country="Ireland",
                icao="EIDW",
                latitude=53.35,
                longitude=-6.27,
                altitude=74,
            ),
            AirportDto(
                id=2,
                iata="LHR",
                name="London Heathrow",
                city="London",
                country="United Kingdom",
                icao="EGLL",
                latitude=51.47,
                longitude=-0.46,
                altitude=25,
            ),
            AirportDto(
                id=3,
                iata="CDG",
                name="Paris Charles de Gaulle",
                city="Paris",
                country="France",
                icao="LFPG",
                latitude=49.01,
                longitude=2.55,
                altitude=119,
            ),
            AirportDto(
                id=4,
                iata="AMS",
                name="Amsterdam Schiphol",
                city="Amsterdam",
                country="Netherlands",
                icao="EHAM",
                latitude=52.31,
                longitude=4.77,
                altitude=-3,
            ),
        ]

    @pytest.fixture
    def home_airport(self):
        return AirportDto(
            id=1,
            iata="DUB",
            name="Dublin",
            city="Dublin",
            country="Ireland",
            icao="EIDW",
            latitude=53.35,
            longitude=-6.27,
            altitude=74,
        )

    def test_returns_none_when_airports_empty(self, home_airport):
        result = try_generate_sequence([], home_airport, 1)

        assert result is None

    def test_returns_daily_sequence_dto_on_success(self, airports, home_airport):
        result = try_generate_sequence(airports, home_airport, 1)

        assert result is None or isinstance(result, DailySequenceDto)

    def test_sequence_starts_between_0005_and_0200(self, airports, home_airport):
        # Run multiple times to increase chance of success
        for _ in range(10):
            result = try_generate_sequence(airports, home_airport, 1)
            if result:
                first_gate_open = result.routes[0].estimated_gate_open_time
                hour = first_gate_open.hour
                minute = first_gate_open.minute

                assert (hour == 0 and minute >= 5) or (hour == 1) or (hour == 2 and minute == 0)
                break

    def test_sequence_returns_to_home_airport(self, airports, home_airport):
        for _ in range(10):
            result = try_generate_sequence(airports, home_airport, 1)
            if result:
                assert result.routes[-1].destination_iata == home_airport.iata
                break

    def test_sequence_has_correct_number_of_flights(self, airports, home_airport):
        for _ in range(10):
            result = try_generate_sequence(airports, home_airport, 1)
            if result:
                assert 2 <= len(result.routes) <= 8
                break

    def test_takeoff_80_to_110_minutes_after_gate_open(self, airports, home_airport):
        for _ in range(10):
            result = try_generate_sequence(airports, home_airport, 1)
            if result:
                route = result.routes[0]
                gate_open = datetime.combine(date.today(), route.estimated_gate_open_time)
                takeoff = datetime.combine(date.today(), route.estimated_takeoff_time)

                duration_minutes = (takeoff - gate_open).total_seconds() / 60
                assert 80 <= duration_minutes <= 110
                break

    def test_final_landing_after_1800(self, airports, home_airport):
        for _ in range(10):
            result = try_generate_sequence(airports, home_airport, 1)
            if result:
                final_landing = result.routes[-1].estimated_arrival_time
                assert final_landing.hour >= 18
                break


class TestGenerateAircraftDailySequences:
    @pytest.fixture
    def airports(self):
        return [
            AirportDto(
                id=1,
                iata="DUB",
                name="Dublin",
                city="Dublin",
                country="Ireland",
                icao="EIDW",
                latitude=53.35,
                longitude=-6.27,
                altitude=74,
            ),
            AirportDto(
                id=2,
                iata="LHR",
                name="London Heathrow",
                city="London",
                country="United Kingdom",
                icao="EGLL",
                latitude=51.47,
                longitude=-0.46,
                altitude=25,
            ),
            AirportDto(
                id=3,
                iata="CDG",
                name="Paris Charles de Gaulle",
                city="Paris",
                country="France",
                icao="LFPG",
                latitude=49.01,
                longitude=2.55,
                altitude=119,
            ),
        ]

    def test_raises_error_when_airports_empty(self):
        with pytest.raises(ValueError, match="airports list is empty"):
            generate_aircraft_daily_sequences([], 1)

    def test_returns_daily_sequence_dto(self, airports):
        result = generate_aircraft_daily_sequences(airports, 1)

        assert isinstance(result, DailySequenceDto)

    def test_sets_correct_sequence_id(self, airports):
        result = generate_aircraft_daily_sequences(airports, 42)

        assert result.sequence_id == 42

    def test_selects_home_airport_from_list(self, airports):
        result = generate_aircraft_daily_sequences(airports, 1)

        airport_iatas = [a.iata for a in airports]
        assert result.home_airport_iata in airport_iatas


class TestGenerateDepartureDelayScenario:
    def test_returns_dataframe(self):
        result = generate_departure_delay_scenario(1)

        assert isinstance(result, pd.DataFrame)

    def test_has_required_columns(self):
        result = generate_departure_delay_scenario(1)

        required_columns = [
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
        ]

        for col in required_columns:
            assert col in result.columns

    def test_scenario_id_matches_input(self):
        result = generate_departure_delay_scenario(42)

        assert (result["scenario_id"] == 42).all()

    def test_event_ids_are_sequential(self):
        result = generate_departure_delay_scenario(1)

        event_ids = result["event_id"].tolist()
        assert event_ids == list(range(len(event_ids)))

    def test_timestamps_increment_by_60_seconds(self):
        result = generate_departure_delay_scenario(1)

        timestamps = result["event_timestamp_in_seconds"].tolist()
        for i in range(1, len(timestamps)):
            assert timestamps[i] - timestamps[i - 1] == 60

    def test_weather_events_are_valid(self):
        result = generate_departure_delay_scenario(1)

        valid_weather = ["clear", "rain", "snow", "fog", "thunderstorm"]
        assert result["weather_event"].isin(valid_weather).all()

    def test_runway_condition_is_valid(self):
        result = generate_departure_delay_scenario(1)

        valid_conditions = ["wet", "dry"]
        assert result["runway_condition"].isin(valid_conditions).all()

    def test_aircraft_type_is_valid(self):
        result = generate_departure_delay_scenario(1)

        valid_aircraft = ["A320", "A321", "B737"]
        assert result["aircraft_type"].isin(valid_aircraft).all()

    def test_has_gate_open_event(self):
        result = generate_departure_delay_scenario(1)

        assert "gate_open" in result["air_traffic_event"].values

    def test_has_takeoff_event(self):
        result = generate_departure_delay_scenario(1)

        assert "takeoff" in result["air_traffic_event"].values

    def test_passenger_load_between_0_and_100(self):
        result = generate_departure_delay_scenario(1)

        assert (result["passenger_load_percent"] >= 0).all()
        assert (result["passenger_load_percent"] <= 100).all()


class TestGenerateDepartureDelayModel:
    def test_returns_dataframe(self):
        result = generate_departure_delay_model("DUB", num_scenarios=5)

        assert isinstance(result, pd.DataFrame)

    def test_generates_correct_number_of_scenarios(self):
        num_scenarios = 10
        result = generate_departure_delay_model("DUB", num_scenarios=num_scenarios)

        unique_scenarios = result["scenario_id"].nunique()
        assert unique_scenarios == num_scenarios

    def test_returns_empty_dataframe_when_no_scenarios(self):
        result = generate_departure_delay_model("DUB", num_scenarios=0)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0


class TestSaveDepartureToParquet:
    @patch("os.makedirs")
    @patch("pandas.DataFrame.to_parquet")
    def test_creates_directory(self, mock_to_parquet, mock_makedirs):
        df = pd.DataFrame({"col1": [1, 2, 3]})

        save_departure_to_parquet(df, "DUB", "/test/path")

        mock_makedirs.assert_called_once_with("/test/path", exist_ok=True)

    @patch("os.makedirs")
    @patch("pandas.DataFrame.to_parquet")
    def test_saves_with_correct_filename(self, mock_to_parquet, mock_makedirs):
        df = pd.DataFrame({"col1": [1, 2, 3]})

        save_departure_to_parquet(df, "DUB", "/test/path")

        mock_to_parquet.assert_called_once_with("/test/path/DUB.parquet", index=False)


class TestGenerateLandingDelayScenario:
    def test_returns_dataframe(self):
        result = generate_landing_delay_scenario(1)

        assert isinstance(result, pd.DataFrame)

    def test_has_required_columns(self):
        result = generate_landing_delay_scenario(1)

        required_columns = [
            "scenario_id",
            "event_id",
            "event_timestamp_in_seconds",
            "temperature_celsius",
            "wind_speed_kmh",
            "precipitation_mm",
            "visibility_km",
            "weather_event",
            "air_traffic_event",
        ]

        for col in required_columns:
            assert col in result.columns

    def test_scenario_id_matches_input(self):
        result = generate_landing_delay_scenario(42)

        assert (result["scenario_id"] == 42).all()

    def test_event_ids_are_sequential(self):
        result = generate_landing_delay_scenario(1)

        event_ids = result["event_id"].tolist()
        assert event_ids == list(range(len(event_ids)))

    def test_timestamps_are_60_seconds_apart(self):
        result = generate_landing_delay_scenario(1)

        timestamps = result["event_timestamp_in_seconds"].tolist()
        expected = [i * 60 for i in range(len(timestamps))]
        assert timestamps == expected

    def test_respects_max_events_limit(self):
        max_events = 50
        result = generate_landing_delay_scenario(1, max_events=max_events)

        assert len(result) <= max_events

    def test_weather_events_are_valid(self):
        result = generate_landing_delay_scenario(1)

        valid_weather = ["clear", "rain", "snow", "fog", "thunderstorm"]
        assert result["weather_event"].isin(valid_weather).all()

    def test_air_traffic_events_are_valid(self):
        result = generate_landing_delay_scenario(1)

        valid_events = ["landing_approved", "hold_for_weather", "hold_for_traffic"]
        assert result["air_traffic_event"].isin(valid_events).all()

    def test_final_event_is_landing_approved(self):
        result = generate_landing_delay_scenario(1)

        last_event = result.iloc[-1]["air_traffic_event"]
        assert last_event == "landing_approved"


class TestGenerateLandingDelayModel:
    def test_returns_dataframe(self):
        result = generate_landing_delay_model("DUB", num_scenarios=5)

        assert isinstance(result, pd.DataFrame)

    def test_generates_correct_number_of_scenarios(self):
        num_scenarios = 10
        result = generate_landing_delay_model("DUB", num_scenarios=num_scenarios)

        unique_scenarios = result["scenario_id"].nunique()
        assert unique_scenarios == num_scenarios

    def test_returns_empty_dataframe_when_no_scenarios(self):
        result = generate_landing_delay_model("DUB", num_scenarios=0)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_all_scenarios_have_landing_approved(self):
        result = generate_landing_delay_model("DUB", num_scenarios=5)

        for scenario_id in result["scenario_id"].unique():
            scenario_data = result[result["scenario_id"] == scenario_id]
            last_event = scenario_data.iloc[-1]["air_traffic_event"]
            assert last_event == "landing_approved"


class TestSaveLandingToParquet:
    @patch("pandas.DataFrame.to_parquet")
    def test_saves_with_correct_filename(self, mock_to_parquet):
        df = pd.DataFrame({"col1": [1, 2, 3]})

        save_landing_to_parquet(df, "DUB", "/test/path")

        mock_to_parquet.assert_called_once_with("/test/path/DUB.parquet", index=False)


class TestDataGeneratorIntegration:
    """Integration tests to verify data generators work together"""

    def test_departure_and_landing_models_have_compatible_schemas(self):
        departure_df = generate_departure_delay_model("DUB", num_scenarios=2)
        landing_df = generate_landing_delay_model("DUB", num_scenarios=2)

        # Common columns should exist in both
        common_columns = [
            "scenario_id",
            "event_id",
            "event_timestamp_in_seconds",
            "temperature_celsius",
            "wind_speed_kmh",
            "precipitation_mm",
            "visibility_km",
            "weather_event",
            "air_traffic_event",
        ]

        for col in common_columns:
            assert col in departure_df.columns
            assert col in landing_df.columns

    @pytest.mark.parametrize("num_scenarios", [1, 5, 10])
    def test_generators_handle_different_scenario_counts(self, num_scenarios):
        departure_df = generate_departure_delay_model("DUB", num_scenarios=num_scenarios)
        landing_df = generate_landing_delay_model("DUB", num_scenarios=num_scenarios)

        assert departure_df["scenario_id"].nunique() == num_scenarios
        assert landing_df["scenario_id"].nunique() == num_scenarios
