"""
Type definitions for update_trial_metadata command.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import strawberry
from pydantic import BaseModel, field_validator
from strawberry.experimental.pydantic import input as pydantic_input


class UpdateTrialMetadataInputModel(BaseModel):
    """Pydantic model for update trial metadata with validation."""
    trial_id: str
    name: Optional[str] = None
    phase: Optional[str] = None
    expected_updated_at: Optional[datetime] = None

    @field_validator('trial_id')
    @classmethod
    def validate_trial_id(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError('trial_id cannot be empty')
        return v

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v.strip()) == 0:
            raise ValueError('name cannot be empty')
        return v


# Strawberry GraphQL input generated from Pydantic model
@pydantic_input(model=UpdateTrialMetadataInputModel, all_fields=True)
class UpdateTrialMetadataInput:
    """GraphQL input for updating trial metadata (backed by Pydantic)."""
    pass


@strawberry.type
@dataclass
class UpdateTrialMetadataResponse:
    """Response from updating trial metadata."""
    id: str
    name: str
    phase: str
    status: str
    updated_at: datetime
    created_at: datetime
    changes: str  # Human-readable summary of changes
