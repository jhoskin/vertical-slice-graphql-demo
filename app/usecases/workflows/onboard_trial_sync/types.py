"""
Type definitions for synchronous onboard trial saga.
"""
from dataclasses import dataclass
from typing import Optional

import strawberry


@strawberry.input
class SiteInput:
    """Site input for onboarding."""
    name: str
    country: str


@strawberry.input
class OnboardTrialSyncInput:
    """Input for synchronous trial onboarding saga."""
    name: str
    phase: str
    initial_protocol_version: str
    sites: list[SiteInput]


@strawberry.type
@dataclass
class OnboardTrialSyncResponse:
    """Response from synchronous trial onboarding saga."""
    success: bool
    trial_id: Optional[int]
    message: str
    steps_completed: list[str]  # Which steps succeeded before failure (if any)
