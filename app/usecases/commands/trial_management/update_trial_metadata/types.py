"""
Type definitions for update_trial_metadata command.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import strawberry


@strawberry.input
class UpdateTrialMetadataInput:
    """Input for updating trial metadata."""
    trial_id: int
    name: Optional[str] = None
    phase: Optional[str] = None


@strawberry.type
@dataclass
class UpdateTrialMetadataResponse:
    """Response from updating trial metadata."""
    id: int
    name: str
    phase: str
    status: str
    created_at: datetime
    changes: str  # Human-readable summary of changes
