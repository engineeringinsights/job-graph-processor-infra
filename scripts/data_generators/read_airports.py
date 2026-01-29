import csv

from service.models.airport import AirportDto


def read_airports_csv(file_path: str) -> list[AirportDto]:
    airports = []
    with open(file_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            try:
                airport = AirportDto(
                    id=int(row[0]),
                    name=row[1],
                    city=row[2],
                    country=row[3],
                    iata=row[4],
                    icao=row[5],
                    latitude=float(row[6]),
                    longitude=float(row[7]),
                    altitude=int(row[8]),
                    timezone=float(row[9]),
                    dst=row[10],
                    tz_database_time_zone=row[11],
                    airport_type=row[12],
                    source=row[13],
                )
                airports.append(airport)
            except (ValueError, IndexError):
                continue

    return airports[:10]
