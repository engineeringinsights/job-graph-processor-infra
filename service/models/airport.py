from pydantic import BaseModel


class AirportDto(BaseModel):

    id: int
    name: str
    city: str
    country: str
    iata: str
    icao: str
    latitude: float
    longitude: float
    altitude: int
