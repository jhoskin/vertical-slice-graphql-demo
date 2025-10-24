"""
Type definitions for synchronous onboard trial saga.
"""
from dataclasses import dataclass
from typing import Optional

import strawberry
from pydantic import BaseModel, field_validator
from strawberry.experimental.pydantic import input as pydantic_input


class SiteInputModel(BaseModel):
    """Site input for onboarding."""
    name: str
    country: str

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError('name cannot be empty')
        return v

    @field_validator('country')
    @classmethod
    def validate_country(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError('country cannot be empty')
        return v


# GraphQL input type for SiteInput
@pydantic_input(model=SiteInputModel, all_fields=True)
class SiteInput:
    """GraphQL input for site (backed by Pydantic)."""
    pass


class OnboardTrialSyncInputModel(BaseModel):
    """Input for synchronous trial onboarding saga."""
    name: str
    phase: str
    initial_protocol_version: str
    sites: list[SiteInputModel]

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError('name cannot be empty')
        return v

    @field_validator('phase')
    @classmethod
    def validate_phase(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError('phase cannot be empty')
        return v

    @field_validator('initial_protocol_version')
    @classmethod
    def validate_protocol_version(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError('initial_protocol_version cannot be empty')
        return v

    # Note: Empty sites list is allowed - trials can be onboarded without sites initially


# GraphQL input type for OnboardTrialSyncInput
@pydantic_input(model=OnboardTrialSyncInputModel, all_fields=True)
class OnboardTrialSyncInput:
    """GraphQL input for synchronous trial onboarding (backed by Pydantic)."""
    pass


@strawberry.type
@dataclass
class OnboardTrialSyncResponse:
    """Response from synchronous trial onboarding saga."""
    success: bool
    trial_id: Optional[int]
    message: str
    steps_completed: list[str]  # Which steps succeeded before failure (if any)
