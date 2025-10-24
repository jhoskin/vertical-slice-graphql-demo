"""
GraphQL resolver for update_trial_metadata_via_vo mutation.

This demonstrates the Virtual Object approach for concurrency protection.
Compare with the original updateTrialMetadata mutation to see the difference.
"""
import os
from datetime import datetime

import httpx
import strawberry

from app.usecases.commands.trial_management.update_trial_metadata_via_vo.types import (
    UpdateTrialMetadataInput,
    UpdateTrialMetadataResponse,
)


@strawberry.mutation
async def update_trial_metadata_via_vo(
    input: UpdateTrialMetadataInput,
) -> UpdateTrialMetadataResponse:
    """
    GraphQL mutation to update trial metadata via Virtual Object.

    This mutation uses Restate Virtual Objects for automatic concurrency protection
    combined with optimistic locking for stale data protection.

    All concurrent updates to the same trial are automatically serialized by Restate,
    and version checking prevents updates based on stale data.

    Benefits:
    - Automatic serialization of concurrent writes per trial_id
    - Version checking prevents stale data updates
    - Scales across multiple app instances
    - Clean separation of concurrency control from business logic

    Args:
        input: Update input with trial_id, optional name/phase, and optional expected_version

    Returns:
        Updated trial data with change summary
    """
    # Convert Strawberry-wrapped input to validated Pydantic model
    validated_input = input.to_pydantic()

    # Prepare update data for virtual object
    update_data = {}
    if validated_input.name is not None:
        update_data["name"] = validated_input.name
    if validated_input.phase is not None:
        update_data["phase"] = validated_input.phase
    if validated_input.expected_updated_at is not None:
        update_data["expected_updated_at"] = validated_input.expected_updated_at.isoformat()

    # Get Restate URL from environment
    restate_url = os.getenv("RESTATE_URL", "http://localhost:8080")

    # Call Virtual Object directly via Restate HTTP API
    # The trial_id is the key - Restate serializes all calls with the same key
    #
    # NOTE: The Python SDK for Restate doesn't currently provide a client library
    # for invoking Restate services from outside a Restate context (ctx.object_call()
    # only works from within Restate handlers). The TypeScript SDK does provide this
    # via @restatedev/restate-sdk-clients, and this capability may become available
    # in the Python SDK in the future. For now, HTTP invocation is the recommended
    # approach for calling Restate services from regular Python code.
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{restate_url}/TrialVirtualObject/{validated_input.trial_id}/update_metadata",
            json=update_data,
        )

        # Check for errors and propagate terminal errors (like StaleDataError) properly
        if response.status_code != 200:
            # Try to extract error message from Restate response
            try:
                error_data = response.json()
                error_message = error_data.get("message", str(response.text))
            except Exception:
                error_message = response.text

            # Re-raise terminal errors with proper message for GraphQL
            from app.usecases.commands.trial_management._errors import StaleDataError
            if any(keyword in error_message.lower() for keyword in ["version mismatch", "stale", "timestamp mismatch"]):
                raise StaleDataError(error_message)

            # For other errors, raise generic HTTP error
            response.raise_for_status()

        result = response.json()

    # Convert response back to UpdateTrialMetadataResponse
    return UpdateTrialMetadataResponse(
        id=result["id"],
        name=result["name"],
        phase=result["phase"],
        status=result["status"],
        updated_at=datetime.fromisoformat(result["updated_at"]),
        created_at=datetime.fromisoformat(result["created_at"]),
        changes=result["changes"],
    )
