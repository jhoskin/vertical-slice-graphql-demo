"""
Webhook endpoint for receiving workflow progress updates from Restate.

This endpoint receives HTTP POST requests from the Restate workflow
and publishes strongly-typed progress updates to the GraphQL subscription system.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.usecases.workflows.onboard_trial_async.pubsub import workflow_pubsub
from app.usecases.workflows.onboard_trial_async.types import (
    OnboardTrialProgressUpdate,
    OnboardTrialStatus,
    TrialData,
    SiteProgress,
    WorkflowError,
)

router = APIRouter()


class TrialDataPayload(BaseModel):
    """Trial entity data in webhook payload."""
    id: int
    name: str
    phase: str


class SiteProgressPayload(BaseModel):
    """Site progress data in webhook payload."""
    current_site_index: int
    total_sites: int
    site_name: str


class WorkflowErrorPayload(BaseModel):
    """Error details in webhook payload."""
    failed_step: str
    error_message: str


class ProgressWebhookPayload(BaseModel):
    """Strongly-typed payload sent from Restate workflow to webhook."""

    workflow_id: str
    status: str  # Will be converted to enum
    message: str
    trial: TrialDataPayload | None = None
    site_progress: SiteProgressPayload | None = None
    error: WorkflowErrorPayload | None = None


@router.post("/api/workflows/progress")
async def workflow_progress_webhook(payload: ProgressWebhookPayload):
    """
    Webhook endpoint for Restate workflow progress updates.

    This endpoint is called by the Restate workflow via durable HTTP POST
    to notify subscribers of strongly-typed progress including trial data,
    site registration details, and error information.

    Args:
        payload: Detailed progress update data from workflow

    Returns:
        Success acknowledgment
    """
    # Convert status string to enum
    status_enum = OnboardTrialStatus(payload.status)

    # Convert optional nested data
    trial_data = None
    if payload.trial:
        trial_data = TrialData(
            id=payload.trial.id,
            name=payload.trial.name,
            phase=payload.trial.phase,
        )

    site_progress = None
    if payload.site_progress:
        site_progress = SiteProgress(
            current_site_index=payload.site_progress.current_site_index,
            total_sites=payload.site_progress.total_sites,
            site_name=payload.site_progress.site_name,
        )

    error_data = None
    if payload.error:
        error_data = WorkflowError(
            failed_step=payload.error.failed_step,
            error_message=payload.error.error_message,
        )

    # Create strongly-typed update
    update = OnboardTrialProgressUpdate(
        workflow_id=payload.workflow_id,
        status=status_enum,
        message=payload.message,
        trial=trial_data,
        site_progress=site_progress,
        error=error_data,
    )

    # Publish to all subscribers
    await workflow_pubsub.publish(update)

    return {"status": "ok"}
