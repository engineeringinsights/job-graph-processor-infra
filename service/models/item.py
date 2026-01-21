"""
Item models for request/response validation.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CreateItemRequest:
    """Request model for creating an item."""

    pk: str
    sk: str
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate the request after initialization."""
        if not self.pk:
            raise ValueError("pk is required")
        if not self.sk:
            raise ValueError("sk is required")


@dataclass
class ItemResponse:
    """Response model for an item."""

    pk: str
    sk: str
    data: dict[str, Any] = field(default_factory=dict)
