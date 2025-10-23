"""
Webhook endpoint for receiving workflow progress updates from Restate.

This endpoint receives HTTP POST requests from the Restate workflow
and publishes them to the GraphQL subscription system.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.usecases.workflows.onboard_trial_async.pubsub import workflow_pubsub
from app.usecases.workflows.onboard_trial_async.types import WorkflowProgressUpdate

router = APIRouter()


class ProgressWebhookPayload(BaseModel):
    """Payload sent from Restate workflow to webhook."""

    workflow_id: str
    status: str
    message: str
    trial_id: int | None = None


@router.post("/api/workflows/progress")
async def workflow_progress_webhook(payload: ProgressWebhookPayload):
    """
    Webhook endpoint for Restate workflow progress updates.

    This endpoint is called by the Restate workflow via durable HTTP POST
    to notify subscribers of workflow progress.

    Args:
        payload: Progress update data from workflow

    Returns:
        Success acknowledgment
    """
    # Convert to progress update type
    update = WorkflowProgressUpdate(
        workflow_id=payload.workflow_id,
        status=payload.status,
        message=payload.message,
        trial_id=payload.trial_id,
    )

    # Publish to all subscribers
    await workflow_pubsub.publish(update)

    return {"status": "ok"}
