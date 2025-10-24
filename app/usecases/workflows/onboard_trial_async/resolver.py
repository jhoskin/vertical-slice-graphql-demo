"""
GraphQL resolver for asynchronous trial onboarding workflow.

Provides:
- Mutation to start the workflow (returns immediately)
- Subscription to receive progress updates
"""
import asyncio
import os
import uuid
from typing import AsyncGenerator

import httpx
import strawberry

from app.usecases.workflows.onboard_trial_async.pubsub import workflow_pubsub
from app.usecases.workflows.onboard_trial_async.types import (
    OnboardTrialAsyncInput,
    OnboardTrialAsyncResponse,
    WorkflowProgressUpdate,
)


@strawberry.mutation
async def start_onboard_trial_async(
    input: OnboardTrialAsyncInput,
) -> OnboardTrialAsyncResponse:
    """
    GraphQL mutation to start async trial onboarding workflow.

    This mutation returns immediately with a workflow ID. The actual
    onboarding happens asynchronously via Restate. Subscribe to
    'workflowProgress' to receive updates.

    Args:
        input: Onboarding input with trial, protocol, and sites

    Returns:
        Immediate response with workflow ID
    """
    # Generate unique workflow ID
    workflow_id = str(uuid.uuid4())

    # Prepare input for Restate workflow
    workflow_input = {
        "name": input.name,
        "phase": input.phase,
        "initial_protocol_version": input.initial_protocol_version,
        "sites": [{"name": site.name, "country": site.country} for site in input.sites],
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
        message=f"Workflow started for trial '{input.name}'. Use workflow ID to subscribe to progress.",
    )


@strawberry.subscription
async def workflow_progress(
    workflow_id: str,
) -> AsyncGenerator[WorkflowProgressUpdate, None]:
    """
    GraphQL subscription to receive workflow progress updates.

    Subscribe with the workflow ID received from 'startOnboardTrialAsync'
    mutation. Updates are streamed in real-time as the workflow progresses.

    Args:
        workflow_id: The workflow ID to subscribe to

    Yields:
        Progress updates from the workflow
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
            if update.status in ("completed", "failed"):
                break

    except asyncio.CancelledError:
        # Client unsubscribed
        pass
    finally:
        # Clean up subscription
        workflow_pubsub.unsubscribe(workflow_id, queue)
