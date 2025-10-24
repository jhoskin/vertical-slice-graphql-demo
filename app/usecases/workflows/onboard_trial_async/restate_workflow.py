"""
Restate workflow for asynchronous trial onboarding.

This workflow uses durable execution to ensure progress is never lost.
Each step is durably recorded, and the workflow can resume from any point.

GraphQL operations are wrapped with automatic retry logic via the
infrastructure GraphQL client, which filters terminal vs transient errors.

Progress updates are published via GraphQL mutation to the pub/sub system.
"""
import logging
from datetime import timedelta

from restate import Workflow, WorkflowContext

from app.infrastructure.graphql_client import execute_graphql_mutation, get_api_url
from app.usecases.workflows.onboard_trial_async.types import (
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

    # Capture API URL deterministically at workflow start
    # This ensures the same URL is used on replay even if env vars change
    api_url = get_api_url()

    # Extract input data
    trial_name = input_data["name"]
    trial_phase = input_data["phase"]
    protocol_version = input_data["initial_protocol_version"]
    sites = input_data["sites"]
    logger.info(f"[WORKFLOW {workflow_id}] Input: name={trial_name}, phase={trial_phase}, sites={len(sites)}")

    # Track current step for better error reporting
    current_step = "trial_creation"

    try:
        # Step 1: Create trial
        await _send_progress(
            ctx,
            workflow_id,
            "0_creating_trial",
            OnboardTrialStatus.CREATING_TRIAL,
            "Creating trial...",
            api_url,
        )

        # Add synthetic delay for human observation
        await ctx.sleep(timedelta(seconds=2))

        # Create trial via GraphQL API with durable execution
        logger.info(f"[WORKFLOW {workflow_id}] Creating trial via GraphQL API")

        # Define async function for ctx.run_typed - Restate will durably track this
        async def create_trial_mutation():
            return await execute_graphql_mutation(
                "mutation CreateTrial($input: CreateTrialInput!) { createTrial(input: $input) { id } }",
                {"input": {"name": trial_name, "phase": trial_phase}},
                api_url,  # Use captured URL for determinism
                log_prefix=f"[WORKFLOW {workflow_id}]"
            )

        trial_result = await ctx.run("create_trial", create_trial_mutation)
        trial_id = trial_result["data"]["createTrial"]["id"]
        logger.info(f"[WORKFLOW {workflow_id}] Trial created successfully with ID: {trial_id}")

        # Create trial data structure for progress updates
        trial_data = TrialData(id=trial_id, name=trial_name, phase=trial_phase)

        await _send_progress(
            ctx,
            workflow_id,
            "1_trial_created",
            OnboardTrialStatus.TRIAL_CREATED,
            f"Trial '{trial_name}' created with ID {trial_id}",
            api_url,
            trial=trial_data,
        )

        # Step 2: Add protocol version
        current_step = "protocol_creation"
        await ctx.sleep(timedelta(seconds=2))

        await _send_progress(
            ctx,
            workflow_id,
            "2_protocol_adding",
            OnboardTrialStatus.PROTOCOL_ADDING,
            f"Adding protocol version {protocol_version}...",
            api_url,
            trial=trial_data,
        )

        # Add protocol with ctx.run() for durable execution
        logger.info(f"[WORKFLOW {workflow_id}] Adding protocol {protocol_version} to trial {trial_id}")
        protocol_result = await ctx.run(
            "add_protocol",
            lambda: _add_protocol(trial_id, protocol_version, trial_name)
        )
        logger.info(f"[WORKFLOW {workflow_id}] Protocol added: {protocol_result}")

        await _send_progress(
            ctx,
            workflow_id,
            "3_protocol_added",
            OnboardTrialStatus.PROTOCOL_ADDED,
            f"Protocol version {protocol_version} added to trial",
            api_url,
            trial=trial_data,
        )

        # Step 3: Register sites
        current_step = "site_registration"
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
                workflow_id,
                f"4_site_{i}_registering",
                OnboardTrialStatus.SITE_REGISTERING,
                f"Registering site {site['name']} ({i+1}/{len(sites)})...",
                api_url,
                trial=trial_data,
                site_progress=site_prog,
            )

            # Register site with ctx.run() for durable execution
            logger.info(f"[WORKFLOW {workflow_id}] Registering site {i+1}/{len(sites)}: {site['name']}, {site['country']}")
            site_result = await ctx.run(
                f"register_site_{i}",
                lambda site_name=site["name"], country=site["country"]: _register_site(trial_id, site_name, country)
            )
            logger.info(f"[WORKFLOW {workflow_id}] Site registered: {site_result}")

            await _send_progress(
                ctx,
                workflow_id,
                f"5_site_{i}_registered",
                OnboardTrialStatus.SITE_REGISTERED,
                f"Site {site['name']} registered successfully ({i+1}/{len(sites)})",
                api_url,
                trial=trial_data,
                site_progress=site_prog,
            )

        # All steps completed
        logger.info(f"[WORKFLOW {workflow_id}] All steps completed successfully")
        await _send_progress(
            ctx,
            workflow_id,
            "6_completed",
            OnboardTrialStatus.COMPLETED,
            f"Successfully onboarded trial '{trial_name}' with {len(sites)} sites",
            api_url,
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
        # Workflow failed - use explicitly tracked current_step for accurate error reporting
        logger.error(f"[WORKFLOW {workflow_id}] Workflow failed with exception: {str(e)}", exc_info=True)

        error_details = WorkflowError(
            failed_step=current_step,
            error_message=str(e)
        )

        await _send_progress(
            ctx,
            workflow_id,
            "7_failed",
            OnboardTrialStatus.FAILED,
            f"Workflow failed during {current_step}: {str(e)}",
            api_url,
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
    workflow_id: str,
    step_key: str,
    status: OnboardTrialStatus,
    message: str,
    api_url: str,
    trial: TrialData | None = None,
    site_progress: SiteProgress | None = None,
    error: WorkflowError | None = None,
) -> None:
    """
    Send strongly-typed progress update via GraphQL mutation.

    Sends progress updates to the pub/sub system via a GraphQL mutation,
    which then delivers them to subscribers via GraphQL subscription.

    Uses the shared GraphQL client for consistency and automatic retry logic.

    Wrapped with ctx.run() for durable execution - if workflow restarts,
    progress updates won't be sent multiple times.

    Args:
        ctx: Restate workflow context
        workflow_id: Workflow identifier
        step_key: Unique key for this progress update (ensures idempotency)
        status: Current workflow status
        message: Human-readable status message
        api_url: API endpoint URL (captured deterministically at workflow start)
        trial: Trial entity data (if available)
        site_progress: Site registration progress (if applicable)
        error: Error details (if workflow failed)
    """
    # Build GraphQL mutation input
    mutation = """
        mutation PublishOnboardTrialProgress($input: PublishOnboardTrialProgressInput!) {
            publishOnboardTrialProgress(input: $input) {
                success
                publishedAt
            }
        }
    """

    # Build input variables
    variables = {
        "input": {
            "workflowId": workflow_id,
            "status": status.value,
            "message": message,
        }
    }

    # Add optional fields if present
    if trial:
        variables["input"]["trial"] = {
            "id": trial.id,
            "name": trial.name,
            "phase": trial.phase,
        }
    if site_progress:
        variables["input"]["siteProgress"] = {
            "currentSiteIndex": site_progress.current_site_index,
            "totalSites": site_progress.total_sites,
            "siteName": site_progress.site_name,
        }
    if error:
        variables["input"]["error"] = {
            "failedStep": error.failed_step,
            "errorMessage": error.error_message,
        }

    # Define async function for ctx.run() - Restate will durably track this
    async def publish_progress_mutation():
        return await execute_graphql_mutation(
            mutation,
            variables,
            api_url,
            log_prefix=f"[WORKFLOW {workflow_id}]"
        )

    # Execute with durable tracking using unique step_key
    # Fire-and-forget: we log but don't fail workflow if progress update fails
    try:
        await ctx.run(f"progress_{step_key}", publish_progress_mutation)
    except Exception as e:
        logger.warning(f"[WORKFLOW {workflow_id}] Failed to send progress update: {e}")


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
