"""
Type definitions for list_trials query.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import strawberry


@strawberry.input
class ListTrialsInput:
    """Input for listing trials with filters and pagination."""
    phase: Optional[str] = None
    status: Optional[str] = None
    search: Optional[str] = None  # Search in trial name
    limit: int = 20
    offset: int = 0


@strawberry.type
@dataclass
class TrialSummary:
    """Summary information for a trial in a list."""
    id: int
    name: str
    phase: str
    status: str
    created_at: datetime
    site_count: int  # Number of sites linked to trial


@strawberry.type
@dataclass
class TrialsResponse:
    """Paginated list of trials."""
    items: list[TrialSummary]
    total: int  # Total count for pagination
