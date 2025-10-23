"""
Type definitions for asynchronous onboard trial workflow.
"""
from dataclasses import dataclass
from typing import Optional

import strawberry

# Reuse SiteInput from sync workflow to avoid duplication
from app.usecases.workflows.onboard_trial_sync.types import SiteInput


@strawberry.input
class OnboardTrialAsyncInput:
    """Input for asynchronous trial onboarding workflow."""
    name: str
    phase: str
    initial_protocol_version: str
    sites: list[SiteInput]


@strawberry.type
@dataclass
class OnboardTrialAsyncResponse:
    """Immediate response from async workflow (non-blocking)."""
    workflow_id: str
    message: str


@strawberry.type
@dataclass
class WorkflowProgressUpdate:
    """Progress update for workflow subscription."""
    workflow_id: str
    status: str  # e.g., "trial_created", "protocol_added", "site_registered", "completed", "failed"
    message: str
    trial_id: Optional[int] = None
