"""
Trial Virtual Object for concurrency protection.

This Virtual Object provides automatic serialization of concurrent updates
to the same trial, combined with optimistic locking for stale data protection.

Key benefits:
- All operations on the same trial_id are automatically serialized by Restate
- Version checking prevents updates based on stale data
- Validation and business rules enforced before database writes
- Scalable - Restate handles distribution across multiple instances
"""
import logging

from restate import VirtualObject, ObjectContext

from app.infrastructure.database.session import session_scope
from app.usecases.commands.trial_management.update_trial_metadata.handler import (
    update_trial_metadata_handler,
)
from app.usecases.commands.trial_management.update_trial_metadata.types import (
    UpdateTrialMetadataInputModel,
)

logger = logging.getLogger(__name__)

# Create Restate Virtual Object
# The key is the trial_id - all operations on the same trial are serialized
trial_virtual_object = VirtualObject("TrialVirtualObject")


@trial_virtual_object.handler()
async def update_metadata(ctx: ObjectContext, update_data: dict) -> dict:
    """
    Update trial metadata with automatic concurrency protection.

    Restate guarantees that all calls to this method with the same trial_id
    (ctx.key()) are executed serially, one at a time. Combined with timestamp
    checking in the handler, this provides complete protection against both
    race conditions and stale data updates.

    Args:
        ctx: Restate object context (key is trial_id)
        update_data: Dict with 'name', 'phase', and optional 'expected_updated_at' fields

    Returns:
        Dict with updated trial data and changes summary
    """
    from datetime import datetime

    trial_id = ctx.key()  # Now a UUID string
    logger.info(f"[TrialVO {trial_id}] Updating metadata: {update_data}")

    # Extract update fields
    name = update_data.get("name")
    phase = update_data.get("phase")
    expected_updated_at_str = update_data.get("expected_updated_at")

    # Parse expected_updated_at if provided
    expected_updated_at = None
    if expected_updated_at_str:
        expected_updated_at = datetime.fromisoformat(expected_updated_at_str)

    # Create validated Pydantic input (validation happens in constructor)
    input_data = UpdateTrialMetadataInputModel(
        trial_id=trial_id,
        name=name,
        phase=phase,
        expected_updated_at=expected_updated_at,
    )

    # Call existing handler with database session
    # The handler already has timestamp checking, validation and audit logging
    with session_scope() as session:
        result = update_trial_metadata_handler(session, input_data)

    # Convert response to dict for Restate
    response = {
        "id": result.id,
        "name": result.name,
        "phase": result.phase,
        "status": result.status,
        "updated_at": result.updated_at.isoformat(),
        "created_at": result.created_at.isoformat(),
        "changes": result.changes,
    }

    logger.info(f"[TrialVO {trial_id}] Update complete: {response['changes']}")
    return response
