"""
Type definitions for create_trial command.
"""
from dataclasses import dataclass
from datetime import datetime

import strawberry


@strawberry.input
class CreateTrialInput:
    """Input for creating a trial."""
    name: str
    phase: str


@strawberry.type
@dataclass
class CreateTrialOutput:
    """Output from creating a trial."""
    id: int
    name: str
    phase: str
    status: str
    created_at: datetime
