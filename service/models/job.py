from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ExecType(str, Enum):
    """Execution type for job processing."""

    FIRST = "first"
    INTERMEDIATE = "intermediate"
    LAST = "last"
    AGGREGATION = "aggregation"


class IncomingJob(BaseModel):
    correlation_id: str = Field(..., description="Unique ID linking all jobs in a sequence")
    sequence_id: int = Field(..., description="ID of the sequence this job belongs to")
    exec_type: ExecType = Field(..., description="Type of execution: first, intermediate, last, or aggregation")
    route_index: int = Field(..., description="Index of the route in the sequence (0-based)")
    route_data: dict[str, Any] = Field(..., description="Route data (origin, destination, times)")
    home_airport_iata: str = Field(..., description="Home airport for this sequence")
    total_routes: int = Field(..., description="Total number of routes in the sequence")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class CompletedJob(BaseModel):
    correlation_id: str
    sequence_id: int
    exec_type: ExecType
    route_index: int
    status: str = Field(..., description="Status: success or error")
    processing_time_ms: float = Field(..., description="Time taken to process in milliseconds")
    error_message: str | None = Field(default=None, description="Error message if status is error")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class AggregationJob(BaseModel):
    correlation_id: str
    sequence_id: int
    exec_type: ExecType = Field(default=ExecType.AGGREGATION)
    total_routes: int
    home_airport_iata: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
