"""
Type definitions for register_site_to_trial command.
"""
from dataclasses import dataclass

import strawberry
from pydantic import BaseModel, field_validator
from strawberry.experimental.pydantic import input as pydantic_input


class RegisterSiteToTrialInputModel(BaseModel):
    """Input for registering a site to a trial."""
    trial_id: int
    site_name: str
    country: str

    @field_validator('trial_id')
    @classmethod
    def validate_trial_id(cls, v: int) -> int:
        if v <= 0:
            raise ValueError('trial_id must be positive')
        return v

    @field_validator('site_name')
    @classmethod
    def validate_site_name(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError('site_name cannot be empty')
        return v

    @field_validator('country')
    @classmethod
    def validate_country(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError('country cannot be empty')
        return v


# GraphQL input type generated from Pydantic model
@pydantic_input(model=RegisterSiteToTrialInputModel, all_fields=True)
class RegisterSiteToTrialInput:
    """GraphQL input for registering a site to a trial (backed by Pydantic)."""
    pass


@strawberry.type
@dataclass
class RegisterSiteToTrialResponse:
    """Response from registering a site to a trial."""
    trial_id: int
    site_id: int
    site_name: str
    country: str
    link_status: str
