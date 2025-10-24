"""
Type definitions for asynchronous onboard trial workflow.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import strawberry
from pydantic import BaseModel, field_validator
from strawberry.experimental.pydantic import input as pydantic_input

# Reuse SiteInput from sync workflow to avoid duplication
from app.usecases.workflows.onboard_trial_sync.types import SiteInputModel


@strawberry.enum
class OnboardTrialStatus(Enum):
    """Specific status values for trial onboarding workflow."""
    CREATING_TRIAL = "creating_trial"
    TRIAL_CREATED = "trial_created"
    PROTOCOL_ADDING = "protocol_adding"
    PROTOCOL_ADDED = "protocol_added"
    SITE_REGISTERING = "site_registering"
    SITE_REGISTERED = "site_registered"
    COMPLETED = "completed"
    FAILED = "failed"


@strawberry.type
@dataclass
class TrialData:
    """Trial entity data included in progress updates."""
    id: int
    name: str
    phase: str


@strawberry.type
@dataclass
class SiteProgress:
    """Site registration progress details."""
    current_site_index: int
    total_sites: int
    site_name: str


@strawberry.type
@dataclass
class WorkflowError:
    """Error details when workflow fails."""
    failed_step: str
    error_message: str


class OnboardTrialAsyncInputModel(BaseModel):
    """Input for asynchronous trial onboarding workflow."""
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


# GraphQL input type for OnboardTrialAsyncInput
@pydantic_input(model=OnboardTrialAsyncInputModel, all_fields=True)
class OnboardTrialAsyncInput:
    """GraphQL input for asynchronous trial onboarding (backed by Pydantic)."""
    pass


@strawberry.type
@dataclass
class OnboardTrialAsyncResponse:
    """Immediate response from async workflow (non-blocking)."""
    workflow_id: str
    message: str


@strawberry.type
@dataclass
class OnboardTrialProgressUpdate:
    """
    Progress update specific to trial onboarding workflow.

    Provides detailed, strongly-typed progress information including:
    - Current workflow status (enum)
    - Trial entity data once created
    - Site registration progress details
    - Error information if workflow fails
    """
    workflow_id: str
    status: OnboardTrialStatus
    message: str
    trial: Optional[TrialData] = None
    site_progress: Optional[SiteProgress] = None
    error: Optional[WorkflowError] = None
