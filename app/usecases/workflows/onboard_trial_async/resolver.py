"""
GraphQL resolver for asynchronous trial onboarding workflow.

Provides:
- Mutation to start the workflow (returns immediately)
- Mutation to publish progress updates (called by workflow)
- Subscription to receive workflow-specific progress updates
"""
import asyncio
import os
import uuid
from datetime import datetime
from typing import AsyncGenerator, Optional

import httpx
import strawberry

from app.infrastructure.pubsub import workflow_pubsub
from app.usecases.workflows.onboard_trial_async.types import (
    OnboardTrialAsyncInput,
    OnboardTrialAsyncResponse,
    OnboardTrialProgressUpdate,
    OnboardTrialStatus,
    TrialData,
    SiteProgress,
    WorkflowError,
)


@strawberry.mutation
async def start_onboard_trial_async(
    input: OnboardTrialAsyncInput,
) -> OnboardTrialAsyncResponse:
    """
    GraphQL mutation to start async trial onboarding workflow.

    This mutation returns immediately with a workflow ID. The actual
    onboarding happens asynchronously via Restate. Subscribe to
    'onboard_trial_async_progress' to receive updates.

    Args:
        input: Onboarding input with trial, protocol, and sites (validated via Pydantic)

    Returns:
        Immediate response with workflow ID
    """
    # Convert GraphQL input to validated Pydantic model
    validated_input = input.to_pydantic()

    # Generate unique workflow ID
    workflow_id = str(uuid.uuid4())

    # Prepare input for Restate workflow
    workflow_input = {
        "name": validated_input.name,
        "phase": validated_input.phase,
        "initial_protocol_version": validated_input.initial_protocol_version,
        "sites": [{"name": site.name, "country": site.country} for site in validated_input.sites],
    }

    # Invoke Restate workflow (non-blocking)
    # Use environment variable for Restate URL (docker: restate:8080, local: localhost:8080)
    restate_url = os.getenv("RESTATE_URL", "http://localhost:8080")
    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post(
            f"{restate_url}/OnboardTrialWorkflow/{workflow_id}/run/send",
            json=workflow_input,
        )

    return OnboardTrialAsyncResponse(
        workflow_id=workflow_id,
        message=f"Workflow started for trial '{validated_input.name}'. Use workflow ID to subscribe to progress.",
    )


# Input types for publish mutation
@strawberry.input
class TrialDataInput:
    """Trial entity data in progress update."""
    id: int
    name: str
    phase: str


@strawberry.input
class SiteProgressInput:
    """Site progress data in progress update."""
    current_site_index: int
    total_sites: int
    site_name: str


@strawberry.input
class WorkflowErrorInput:
    """Error details in progress update."""
    failed_step: str
    error_message: str


@strawberry.input
class PublishOnboardTrialProgressInput:
    """
    Input for publishing workflow progress updates.

    Following Apollo best practices: strongly typed input with validation.
    """
    workflow_id: str
    status: str  # OnboardTrialStatus enum value
    message: str
    trial: Optional[TrialDataInput] = None
    site_progress: Optional[SiteProgressInput] = None
    error: Optional[WorkflowErrorInput] = None


@strawberry.type
class PublishProgressResponse:
    """
    Response from publish mutation.

    Following Apollo best practices: return meaningful data so caller
    knows the operation succeeded and when it happened.
    """
    success: bool
    published_at: datetime


@strawberry.mutation
async def publish_onboard_trial_progress(
    input: PublishOnboardTrialProgressInput,
) -> PublishProgressResponse:
    """
    GraphQL mutation to publish workflow progress updates.

    This mutation is called by the Restate workflow to publish progress
    updates to the pub/sub system, which then delivers them to subscribers.

    Following Apollo best practices:
    - Named operation for debugging
    - Strongly typed input
    - Returns meaningful data (success + timestamp)

    Args:
        input: Progress update data

    Returns:
        Confirmation with timestamp
    """
    # Convert status string to enum
    status_enum = OnboardTrialStatus(input.status)

    # Convert optional nested data
    trial_data = None
    if input.trial:
        trial_data = TrialData(
            id=input.trial.id,
            name=input.trial.name,
            phase=input.trial.phase,
        )

    site_progress = None
    if input.site_progress:
        site_progress = SiteProgress(
            current_site_index=input.site_progress.current_site_index,
            total_sites=input.site_progress.total_sites,
            site_name=input.site_progress.site_name,
        )

    error_data = None
    if input.error:
        error_data = WorkflowError(
            failed_step=input.error.failed_step,
            error_message=input.error.error_message,
        )

    # Create strongly-typed update
    update = OnboardTrialProgressUpdate(
        workflow_id=input.workflow_id,
        status=status_enum,
        message=input.message,
        trial=trial_data,
        site_progress=site_progress,
        error=error_data,
    )

    # Publish to all subscribers
    await workflow_pubsub.publish(input.workflow_id, update)

    return PublishProgressResponse(
        success=True,
        published_at=datetime.utcnow(),
    )


@strawberry.subscription
async def onboard_trial_async_progress(
    workflow_id: str,
) -> AsyncGenerator[OnboardTrialProgressUpdate, None]:
    """
    GraphQL subscription for trial onboarding workflow progress.

    Subscribe with the workflow ID received from 'startOnboardTrialAsync'
    mutation. Delivers strongly-typed progress updates including:
    - Workflow status (creating_trial, trial_created, etc.)
    - Trial entity data once created
    - Site registration progress with details
    - Error information if workflow fails

    Following Apollo best practices:
    - Use subscriptions for appropriate use cases (long-running workflow progress)
    - NOT using subscriptions for general cache updates (use queries/polling for that)
    - Clear termination conditions (COMPLETED/FAILED statuses)

    Args:
        workflow_id: The workflow ID to subscribe to

    Yields:
        OnboardTrialProgressUpdate: Detailed progress updates from the workflow
    """
    # Subscribe to the workflow's updates
    queue = await workflow_pubsub.subscribe(workflow_id)

    try:
        # Yield updates as they arrive
        while True:
            update = await queue.get()

            # Yield the update to the client
            yield update

            # If workflow completed or failed, stop
            if update.status in (OnboardTrialStatus.COMPLETED, OnboardTrialStatus.FAILED):
                break

    except asyncio.CancelledError:
        # Client unsubscribed
        pass
    finally:
        # Clean up subscription
        workflow_pubsub.unsubscribe(workflow_id, queue)
