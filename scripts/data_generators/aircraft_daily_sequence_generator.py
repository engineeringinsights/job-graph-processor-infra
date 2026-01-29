import json
import os
import random
from datetime import date, datetime, time, timedelta
from math import atan2, cos, radians, sin, sqrt

from scripts.data_generators.read_airports import read_airports_csv
from service.dal.container import s3_for_models
from service.models.aircraft_daily_sequence_dto import DailySequenceDto, RouteDto
from service.models.airport import AirportDto


def calculate_flight_duration(
    start_longitude, start_latitude, end_longitude, end_latitude, average_speed_kmh
) -> timedelta:
    R = 6371.0

    # Convert coordinates from degrees to radians
    lat1 = radians(start_latitude)
    lon1 = radians(start_longitude)
    lat2 = radians(end_latitude)
    lon2 = radians(end_longitude)

    # Haversine formula to calculate the distance
    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    distance_km = R * c

    # Calculate duration in hours
    duration_hours = distance_km / average_speed_kmh

    duration_hours = timedelta(hours=duration_hours)
    return duration_hours


def try_generate_sequence(
    airports: list[AirportDto],
    home_airport: AirportDto,
    id: int,
    max_attempts: int = 250,
    average_speed_kmh: float = 800.0,
) -> DailySequenceDto | None:
    """Attempt to generate one valid DailySequenceDto for given home airport and date.

    Returns DailySequenceDto on success or None if unable after max_attempts.
    """

    if not airports:
        return None

    # Helper to round a datetime to nearest minute (remove seconds/microseconds)
    def to_min(dt: datetime) -> datetime:
        return dt.replace(second=0, microsecond=0)

    # sample number of flights
    num_flights = random.randint(2, 8)  # nosec B311

    # build route airport sequence: origins and destinations
    # we ensure final destination is home_airport
    # pick intermediate airports (num_flights - 1 destinations excluding final home)
    intermediate_count = max(0, num_flights - 1)
    possible_airports = [a for a in airports if a.iata != home_airport.iata]
    if not possible_airports and intermediate_count > 0:
        # can't build non-home legs
        return None

    intermediate_airports = []
    if intermediate_count > 0:
        # pick intermediate_count airports allowing repeats but not equal to previous sequentially
        for _ in range(intermediate_count - 1):
            intermediate_airports.append(random.choice(possible_airports))  # nosec B311
    # The destinations list: first destination is either an intermediate or home if only 1 flight
    destinations = []
    # For n flights, we need n destinations where last is home
    if num_flights == 1:
        destinations = [home_airport]
    else:
        # For flights > 1, pick (num_flights - 1) - 1 = num_flights -2 intermediates placed before final home
        # Simpler: sample (num_flights -1) airports excluding home, then set final destination home
        sampled = []
        for _ in range(num_flights - 1):
            sampled.append(random.choice(possible_airports))  # nosec B311
        destinations = sampled + [home_airport]

    # Now iterate building datetime events
    routes = []

    # First gate open between 00:05 and 02:00
    todays_date = date.today()
    start_minute = random.randint(5, 120)  # nosec B311
    gate_open_dt = datetime.combine(todays_date, time(hour=0, minute=0)) + timedelta(minutes=start_minute)
    gate_open_dt = to_min(gate_open_dt)

    success = True
    current_origin = home_airport

    for dest_airport in destinations:
        # takeoff between 80 and 110 minutes after gate open
        takeoff_offset = random.randint(80, 110)  # nosec B311
        takeoff_dt = gate_open_dt + timedelta(minutes=takeoff_offset)

        # compute flight duration using haversine estimate
        duration_td = calculate_flight_duration(
            current_origin.longitude,
            current_origin.latitude,
            dest_airport.longitude,
            dest_airport.latitude,
            average_speed_kmh,
        )
        # round duration to nearest minute (ceiling)
        duration_minutes = int(duration_td.total_seconds() / 60)
        if duration_td.total_seconds() % 60:
            duration_minutes += 1
        duration_td = timedelta(minutes=duration_minutes)

        landing_dt = takeoff_dt + duration_td

        # enforce same-day (no overnight arrivals)
        if landing_dt.date() != todays_date:
            success = False
            break

        # record route times (use time objects)
        route = RouteDto(
            origin_iata=current_origin.iata,
            destination_iata=dest_airport.iata,
            estimated_gate_open_time=gate_open_dt.time(),
            estimated_takeoff_time=takeoff_dt.time(),
            estimated_arrival_time=landing_dt.time(),
        )
        routes.append(route)

        # prepare for next leg: gate open at next airport between 10 and 40 minutes after landing
        gate_open_offset_next = random.randint(10, 40)  # nosec B311
        gate_open_dt = landing_dt + timedelta(minutes=gate_open_offset_next)
        gate_open_dt = to_min(gate_open_dt)

        current_origin = dest_airport

    if not success:
        # fail, try again
        return None

    # Validate final landing time is between 16:00 and 23:00 (exclusive of 23:00)
    final_landing_dt = datetime.combine(todays_date, routes[-1].estimated_arrival_time)
    if not (final_landing_dt.hour >= 18 and final_landing_dt.hour < 23):
        # fail, try again
        return None

    # Build DailySequenceDto
    sequence = DailySequenceDto(sequence_id=id, home_airport_iata=home_airport.iata, routes=routes)

    # final validation: ensure sequence returns to home
    if sequence.validate_return_to_home():
        return sequence
    # otherwise retry
    return None


def generate_aircraft_daily_sequences(airports: list[AirportDto], id: int) -> DailySequenceDto:
    if not airports:
        raise ValueError("airports list is empty")

    # pick a random home airport
    home_airport = random.choice(airports)  # nosec B311

    max_outer_attempts = 1000
    for _ in range(max_outer_attempts):
        seq = try_generate_sequence(airports, home_airport, id=id)
        if seq is not None:
            return seq
    raise RuntimeError("Unable to generate valid aircraft daily sequence within allowed attempts")


def main():
    airports = read_airports_csv("./data/airports.csv")
    os.makedirs("./data/sequences", exist_ok=True)
    for i in range(200):
        sequence = generate_aircraft_daily_sequences(airports, i)
        # Save locally
        with open(f"./data/sequences/{i}.json", "w") as f:
            json.dump(sequence.model_dump(), f, default=str, indent=4)
        # Save to S3 using the sequence data access
        s3_for_models(1).sequence_data_access.store_sequence(sequence)
        print(f"Saved sequence {i} for {sequence.home_airport_iata}")


if __name__ == "__main__":
    main()
