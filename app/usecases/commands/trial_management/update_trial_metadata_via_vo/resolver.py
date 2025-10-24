"""
GraphQL resolver for update_trial_metadata_via_vo mutation.

This demonstrates the Virtual Object approach for concurrency protection.
Compare with the original updateTrialMetadata mutation to see the difference.
"""
import strawberry

from app.usecases.commands.trial_management.update_trial_metadata_via_vo.handler import (
    update_trial_metadata_via_vo_handler,
)
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

    This mutation uses Restate Virtual Objects for automatic concurrency protection.
    All concurrent updates to the same trial are automatically serialized by Restate,
    eliminating the need for database-level locking.

    Benefits over traditional approach:
    - No SELECT FOR UPDATE needed
    - No optimistic locking complexity
    - Scales across multiple app instances
    - Clean separation of concurrency control from business logic

    Args:
        input: Update input with trial_id and optional name/phase

    Returns:
        Updated trial data with change summary
    """
    return await update_trial_metadata_via_vo_handler(input)
