"""
Type definitions for onboard_trial workflow.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import strawberry


@strawberry.input
class SiteInput:
    """Site input for onboarding."""
    name: str
    country: str


@strawberry.input
class OnboardTrialInput:
    """Input for onboarding a trial."""
    name: str
    phase: str
    initial_protocol_version: str
    sites: list[SiteInput]


@strawberry.type
@dataclass
class OnboardTrialOutput:
    """Output from starting trial onboarding."""
    saga_id: int
    trial_id: Optional[int]
    state: str
    message: str


@strawberry.type
@dataclass
class OnboardingStatusOutput:
    """Status of an onboarding workflow."""
    saga_id: int
    trial_id: Optional[int]
    state: str
    error: Optional[str]
    created_at: datetime
    updated_at: datetime
