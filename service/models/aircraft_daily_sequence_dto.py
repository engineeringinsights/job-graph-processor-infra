from datetime import time

from pydantic import BaseModel


class RouteDto(BaseModel):
    origin_iata: str
    destination_iata: str
    estimated_gate_open_time: time
    estimated_takeoff_time: time
    estimated_arrival_time: time


class DailySequenceDto(BaseModel):
    sequence_id: int
    home_airport_iata: str
    routes: list[RouteDto]

    def validate_return_to_home(self) -> bool:
        if not self.routes:
            return False
        last_route = self.routes[-1]
        return last_route.destination_iata == self.home_airport_iata
