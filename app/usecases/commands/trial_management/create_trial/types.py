"""
Type definitions for create_trial command.
"""
from dataclasses import dataclass
from datetime import datetime

import strawberry
from pydantic import BaseModel, field_validator
from strawberry.experimental.pydantic import input as pydantic_input


class CreateTrialInputModel(BaseModel):
    """Pydantic model for create trial with validation."""
    name: str
    phase: str

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError('name cannot be empty')
        if len(v) > 255:
            raise ValueError('name cannot exceed 255 characters')
        return v

    @field_validator('phase')
    @classmethod
    def validate_phase(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError('phase cannot be empty')
        return v


# GraphQL input type generated from Pydantic model
@pydantic_input(model=CreateTrialInputModel, all_fields=True)
class CreateTrialInput:
    """GraphQL input for creating a trial (backed by Pydantic)."""
    pass


@strawberry.type
@dataclass
class CreateTrialResponse:
    """Response from creating a trial."""
    id: int
    name: str
    phase: str
    status: str
    version: int
    created_at: datetime
