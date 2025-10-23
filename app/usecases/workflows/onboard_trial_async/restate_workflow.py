"""
Restate workflow for asynchronous trial onboarding.

This workflow uses durable execution to ensure progress is never lost.
Each step is durably recorded, and the workflow can resume from any point.
"""
import httpx
from restate import Service, WorkflowContext
from restate.serde import JsonSerde

from app.usecases.workflows.onboard_trial_async.types import (
    OnboardTrialAsyncInput,
    WorkflowProgressUpdate,
)

# Create Restate service
onboard_trial_workflow = Service("OnboardTrialWorkflow")


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

    # Extract input data
    trial_name = input_data["name"]
    trial_phase = input_data["phase"]
    protocol_version = input_data["initial_protocol_version"]
    sites = input_data["sites"]

    # Webhook endpoint for progress updates
    # Note: This should be configured based on environment
    webhook_url = "http://localhost:8000/api/workflows/progress"

    try:
        # Step 1: Create trial
        await _send_progress(
            ctx,
            webhook_url,
            workflow_id,
            "trial_creating",
            "Creating trial...",
        )

        # Add synthetic delay for human observation
        await ctx.sleep(2.0)

        trial_result = await ctx.run_typed(
            "create_trial",
            JsonSerde,
            lambda: _create_trial(trial_name, trial_phase),
        )
        trial_id = trial_result["id"]

        await _send_progress(
            ctx,
            webhook_url,
            workflow_id,
            "trial_created",
            f"Trial created with ID {trial_id}",
            trial_id,
        )

        # Step 2: Add protocol version
        await ctx.sleep(2.0)

        await _send_progress(
            ctx,
            webhook_url,
            workflow_id,
            "protocol_adding",
            "Adding protocol version...",
            trial_id,
        )

        await ctx.run_typed(
            "add_protocol",
            JsonSerde,
            lambda: _add_protocol(trial_id, protocol_version, trial_name),
        )

        await _send_progress(
            ctx,
            webhook_url,
            workflow_id,
            "protocol_added",
            f"Protocol {protocol_version} added",
            trial_id,
        )

        # Step 3: Register sites
        for i, site in enumerate(sites):
            await ctx.sleep(2.0)

            await _send_progress(
                ctx,
                webhook_url,
                workflow_id,
                "site_registering",
                f"Registering site {site['name']}...",
                trial_id,
            )

            await ctx.run_typed(
                f"register_site_{i}",
                JsonSerde,
                lambda s=site: _register_site(trial_id, s["name"], s["country"]),
            )

            await _send_progress(
                ctx,
                webhook_url,
                workflow_id,
                "site_registered",
                f"Site {site['name']} registered",
                trial_id,
            )

        # All steps completed
        await _send_progress(
            ctx,
            webhook_url,
            workflow_id,
            "completed",
            f"Successfully onboarded trial '{trial_name}' with {len(sites)} sites",
            trial_id,
        )

        return {
            "success": True,
            "trial_id": trial_id,
            "message": f"Workflow completed for trial '{trial_name}'",
        }

    except Exception as e:
        # Workflow failed
        await _send_progress(
            ctx,
            webhook_url,
            workflow_id,
            "failed",
            f"Workflow failed: {str(e)}",
        )

        return {
            "success": False,
            "trial_id": None,
            "message": f"Workflow failed: {str(e)}",
        }


async def _send_progress(
    ctx: WorkflowContext,
    webhook_url: str,
    workflow_id: str,
    status: str,
    message: str,
    trial_id: int | None = None,
) -> None:
    """
    Durably send progress update via HTTP POST.

    This uses ctx.run_typed to ensure the HTTP call is durable - if it fails,
    Restate will retry it. Once it succeeds, it won't be retried on replay.
    """

    async def do_http_post():
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                webhook_url,
                json={
                    "workflow_id": workflow_id,
                    "status": status,
                    "message": message,
                    "trial_id": trial_id,
                },
            )
            response.raise_for_status()
            return {"status": "ok"}

    # Make the HTTP call durable
    await ctx.run_typed(
        f"progress_{status}_{ctx.rand_uuid()}",  # Unique name for each progress update
        JsonSerde,
        do_http_post,
    )


def _create_trial(name: str, phase: str) -> dict:
    """
    Create trial in database (simulated).

    In a real implementation, this would call the database.
    For now, we'll use a simplified approach.
    """
    from app.infrastructure.database.session import session_scope
    from app.usecases.commands.trial_management.create_trial.handler import (
        create_trial_handler,
    )
    from app.usecases.commands.trial_management.create_trial.types import (
        CreateTrialInput,
    )

    with session_scope() as session:
        input_data = CreateTrialInput(name=name, phase=phase)
        result = create_trial_handler(session, input_data)
        return {"id": result.id}


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
        RegisterSiteToTrialInput,
    )

    with session_scope() as session:
        input_data = RegisterSiteToTrialInput(
            trial_id=trial_id,
            site_name=site_name,
            country=country,
        )
        result = register_site_to_trial_handler(session, input_data)
        return {"site_id": result.site_id}
