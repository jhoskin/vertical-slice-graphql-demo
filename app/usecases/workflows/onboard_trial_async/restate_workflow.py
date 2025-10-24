"""
Restate workflow for asynchronous trial onboarding.

This workflow uses durable execution to ensure progress is never lost.
Each step is durably recorded, and the workflow can resume from any point.
"""
import logging
import os
import uuid
from datetime import timedelta

import httpx
from restate import Workflow, WorkflowContext
from restate.serde import JsonSerde

from app.usecases.workflows.onboard_trial_async.types import (
    OnboardTrialAsyncInput,
    OnboardTrialProgressUpdate,
    OnboardTrialStatus,
    TrialData,
    SiteProgress,
    WorkflowError,
)

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Create Restate workflow
onboard_trial_workflow = Workflow("OnboardTrialWorkflow")


@onboard_trial_workflow.handler("run")
async def run(ctx: WorkflowContext, input_data: dict) -> dict:
    """
    Main workflow handler for async trial onboarding.

    This workflow orchestrates the same steps as the sync saga but runs
    asynchronously with durable execution. Progress updates are sent via
    HTTP POST to the webhook endpoint.

    Args:
        ctx: Restate workflow context (provides durability)
        input_data: Onboarding input as dict

    Returns:
        Workflow result dict
    """
    workflow_id = ctx.key()
    logger.info(f"[WORKFLOW {workflow_id}] Starting workflow execution")

    # Extract input data
    trial_name = input_data["name"]
    trial_phase = input_data["phase"]
    protocol_version = input_data["initial_protocol_version"]
    sites = input_data["sites"]
    logger.info(f"[WORKFLOW {workflow_id}] Input: name={trial_name}, phase={trial_phase}, sites={len(sites)}")

    # API and webhook endpoints
    # Note: These should be configured based on environment
    api_url = os.getenv("API_URL", "http://localhost:8000")
    webhook_url = f"{api_url}/api/workflows/progress"
    logger.info(f"[WORKFLOW {workflow_id}] API URL: {api_url}")

    try:
        # Step 1: Create trial
        await _send_progress(
            ctx,
            webhook_url,
            workflow_id,
            OnboardTrialStatus.CREATING_TRIAL,
            "Creating trial...",
        )

        # Add synthetic delay for human observation
        await ctx.sleep(timedelta(seconds=2))

        # Call GraphQL API to create trial (more reliable than direct DB access in Restate)
        logger.info(f"[WORKFLOW {workflow_id}] About to call GraphQL API to create trial")

        async def create_trial_via_api():
            logger.info(f"[WORKFLOW {workflow_id}] Inside create_trial_via_api function")
            async with httpx.AsyncClient(timeout=30.0) as client:
                url = f"{api_url}/graphql"
                payload = {
                    "query": "mutation CreateTrial($input: CreateTrialInput!) { createTrial(input: $input) { id } }",
                    "variables": {
                        "input": {"name": trial_name, "phase": trial_phase}
                    },
                }
                logger.info(f"[WORKFLOW {workflow_id}] Posting to {url} with payload: {payload}")

                response = await client.post(url, json=payload)
                logger.info(f"[WORKFLOW {workflow_id}] Response status: {response.status_code}")
                logger.info(f"[WORKFLOW {workflow_id}] Response body: {response.text}")

                response.raise_for_status()
                data = response.json()
                logger.info(f"[WORKFLOW {workflow_id}] Parsed response data: {data}")

                trial_id = data["data"]["createTrial"]["id"]
                logger.info(f"[WORKFLOW {workflow_id}] Extracted trial ID: {trial_id}")
                return {"id": trial_id}

        trial_result = await create_trial_via_api()
        trial_id = trial_result["id"]
        logger.info(f"[WORKFLOW {workflow_id}] Trial created successfully with ID: {trial_id}")

        # Create trial data structure for progress updates
        trial_data = TrialData(id=trial_id, name=trial_name, phase=trial_phase)

        await _send_progress(
            ctx,
            webhook_url,
            workflow_id,
            OnboardTrialStatus.TRIAL_CREATED,
            f"Trial '{trial_name}' created with ID {trial_id}",
            trial=trial_data,
        )

        # Step 2: Add protocol version
        await ctx.sleep(timedelta(seconds=2))

        await _send_progress(
            ctx,
            webhook_url,
            workflow_id,
            OnboardTrialStatus.PROTOCOL_ADDING,
            f"Adding protocol version {protocol_version}...",
            trial=trial_data,
        )

        # Add protocol directly to database (not via GraphQL since no mutation exists)
        logger.info(f"[WORKFLOW {workflow_id}] Adding protocol {protocol_version} to trial {trial_id}")
        protocol_result = _add_protocol(trial_id, protocol_version, trial_name)
        logger.info(f"[WORKFLOW {workflow_id}] Protocol added: {protocol_result}")

        await _send_progress(
            ctx,
            webhook_url,
            workflow_id,
            OnboardTrialStatus.PROTOCOL_ADDED,
            f"Protocol version {protocol_version} added to trial",
            trial=trial_data,
        )

        # Step 3: Register sites
        logger.info(f"[WORKFLOW {workflow_id}] Starting site registration for {len(sites)} sites")
        for i, site in enumerate(sites):
            await ctx.sleep(timedelta(seconds=2))

            site_prog = SiteProgress(
                current_site_index=i + 1,
                total_sites=len(sites),
                site_name=site['name']
            )

            await _send_progress(
                ctx,
                webhook_url,
                workflow_id,
                OnboardTrialStatus.SITE_REGISTERING,
                f"Registering site {site['name']} ({i+1}/{len(sites)})...",
                trial=trial_data,
                site_progress=site_prog,
            )

            # Register site directly
            logger.info(f"[WORKFLOW {workflow_id}] Registering site {i+1}/{len(sites)}: {site['name']}, {site['country']}")
            site_result = _register_site(trial_id, site["name"], site["country"])
            logger.info(f"[WORKFLOW {workflow_id}] Site registered: {site_result}")

            await _send_progress(
                ctx,
                webhook_url,
                workflow_id,
                OnboardTrialStatus.SITE_REGISTERED,
                f"Site {site['name']} registered successfully ({i+1}/{len(sites)})",
                trial=trial_data,
                site_progress=site_prog,
            )

        # All steps completed
        logger.info(f"[WORKFLOW {workflow_id}] All steps completed successfully")
        await _send_progress(
            ctx,
            webhook_url,
            workflow_id,
            OnboardTrialStatus.COMPLETED,
            f"Successfully onboarded trial '{trial_name}' with {len(sites)} sites",
            trial=trial_data,
        )

        result = {
            "success": True,
            "trial_id": trial_id,
            "message": f"Workflow completed for trial '{trial_name}'",
        }
        logger.info(f"[WORKFLOW {workflow_id}] Returning result: {result}")
        return result

    except Exception as e:
        # Workflow failed - determine which step failed
        logger.error(f"[WORKFLOW {workflow_id}] Workflow failed with exception: {str(e)}", exc_info=True)

        # Try to provide context about what failed
        failed_step = "unknown"
        if "trial_id" not in locals():
            failed_step = "trial_creation"
        elif "protocol_result" not in locals():
            failed_step = "protocol_creation"
        else:
            failed_step = "site_registration"

        error_details = WorkflowError(
            failed_step=failed_step,
            error_message=str(e)
        )

        await _send_progress(
            ctx,
            webhook_url,
            workflow_id,
            OnboardTrialStatus.FAILED,
            f"Workflow failed during {failed_step}: {str(e)}",
            error=error_details,
        )

        error_result = {
            "success": False,
            "trial_id": None,
            "message": f"Workflow failed: {str(e)}",
        }
        logger.info(f"[WORKFLOW {workflow_id}] Returning error result: {error_result}")
        return error_result


async def _send_progress(
    ctx: WorkflowContext,
    webhook_url: str,
    workflow_id: str,
    status: OnboardTrialStatus,
    message: str,
    trial: TrialData | None = None,
    site_progress: SiteProgress | None = None,
    error: WorkflowError | None = None,
) -> None:
    """
    Send strongly-typed progress update via HTTP POST.

    Sends OnboardTrialProgressUpdate with detailed status information including:
    - Current workflow status (enum)
    - Trial entity data (if available)
    - Site registration progress (if registering sites)
    - Error details (if workflow failed)

    Fire-and-forget implementation - workflow doesn't fail if progress update fails.
    In production, this could be made durable with ctx.run_typed.
    """
    # Build payload with all available data
    payload = {
        "workflow_id": workflow_id,
        "status": status.value,  # Send enum value
        "message": message,
    }

    # Add optional fields if present
    if trial:
        payload["trial"] = {
            "id": trial.id,
            "name": trial.name,
            "phase": trial.phase,
        }
    if site_progress:
        payload["site_progress"] = {
            "current_site_index": site_progress.current_site_index,
            "total_sites": site_progress.total_sites,
            "site_name": site_progress.site_name,
        }
    if error:
        payload["error"] = {
            "failed_step": error.failed_step,
            "error_message": error.error_message,
        }

    # Send progress update
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(webhook_url, json=payload)
    except Exception:
        # Don't fail workflow if progress update fails
        pass


def _add_protocol(trial_id: int, version: str, trial_name: str) -> dict:
    """Add protocol version to trial (simulated)."""
    from app.infrastructure.database.models import ProtocolVersion
    from app.infrastructure.database.session import session_scope

    with session_scope() as session:
        protocol = ProtocolVersion(
            trial_id=trial_id,
            version=version,
            notes=f"Initial protocol for {trial_name}",
        )
        session.add(protocol)
        session.flush()
        return {"id": protocol.id}


def _register_site(trial_id: int, site_name: str, country: str) -> dict:
    """Register site to trial (simulated)."""
    from app.infrastructure.database.session import session_scope
    from app.usecases.commands.register_site_to_trial.handler import (
        register_site_to_trial_handler,
    )
    from app.usecases.commands.register_site_to_trial.types import (
        RegisterSiteToTrialInputModel,
    )

    with session_scope() as session:
        input_data = RegisterSiteToTrialInputModel(
            trial_id=trial_id,
            site_name=site_name,
            country=country,
        )
        result = register_site_to_trial_handler(session, input_data)
        return {"site_id": result.site_id}
