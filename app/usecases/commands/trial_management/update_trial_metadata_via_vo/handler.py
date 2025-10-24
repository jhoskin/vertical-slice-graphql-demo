"""
Handler for update_trial_metadata_via_vo command.

This handler demonstrates using Restate Virtual Objects for concurrency protection.
Instead of relying on database locks, Restate automatically serializes all updates
to the same trial_id, providing clean concurrency control at the application level.
"""
import httpx
import os

from app.usecases.commands.trial_management.update_trial_metadata.types import (
    UpdateTrialMetadataInput,
    UpdateTrialMetadataResponse,
)


async def update_trial_metadata_via_vo_handler(
    input_data: UpdateTrialMetadataInput,
) -> UpdateTrialMetadataResponse:
    """
    Update trial metadata via Restate Virtual Object.

    This calls the TrialVirtualObject which provides automatic serialization
    of concurrent updates to the same trial. No database locks needed!

    Args:
        input_data: Update input with trial_id and optional name/phase

    Returns:
        Updated trial data with change summary

    Raises:
        HTTPError: If Restate call fails
        ValidationError: If validation fails (propagated from Virtual Object)
    """
    # Get Restate URL from environment
    restate_url = os.getenv("RESTATE_URL", "http://localhost:8080")

    # Prepare update data
    update_data = {}
    if input_data.name is not None:
        update_data["name"] = input_data.name
    if input_data.phase is not None:
        update_data["phase"] = input_data.phase

    # Call Virtual Object via Restate
    # The trial_id is the key - Restate serializes all calls with the same key
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{restate_url}/TrialVirtualObject/{input_data.trial_id}/update_metadata",
            json=update_data,
        )
        response.raise_for_status()
        result = response.json()

    # Convert response back to UpdateTrialMetadataResponse
    from datetime import datetime

    return UpdateTrialMetadataResponse(
        id=result["id"],
        name=result["name"],
        phase=result["phase"],
        status=result["status"],
        created_at=datetime.fromisoformat(result["created_at"]),
        changes=result["changes"],
    )
