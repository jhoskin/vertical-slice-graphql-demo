"""
Trial Virtual Object for concurrency protection.

This Virtual Object provides automatic serialization of concurrent updates
to the same trial, eliminating the need for database-level locking.

Key benefits:
- All operations on the same trial_id are automatically serialized by Restate
- No need for SELECT FOR UPDATE or optimistic locking in the database
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
    UpdateTrialMetadataInput,
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
    (ctx.key()) are executed serially, one at a time. No database locks needed!

    Args:
        ctx: Restate object context (key is trial_id)
        update_data: Dict with 'name' and/or 'phase' fields

    Returns:
        Dict with updated trial data and changes summary
    """
    trial_id = int(ctx.key())
    logger.info(f"[TrialVO {trial_id}] Updating metadata: {update_data}")

    # Extract update fields
    name = update_data.get("name")
    phase = update_data.get("phase")

    # Create input for existing handler
    input_data = UpdateTrialMetadataInput(
        trial_id=trial_id,
        name=name,
        phase=phase,
    )

    # Call existing handler with database session
    # The handler already has validation and audit logging
    with session_scope() as session:
        result = update_trial_metadata_handler(session, input_data)

    # Convert response to dict for Restate
    response = {
        "id": result.id,
        "name": result.name,
        "phase": result.phase,
        "status": result.status,
        "created_at": result.created_at.isoformat(),
        "changes": result.changes,
    }

    logger.info(f"[TrialVO {trial_id}] Update complete: {response['changes']}")
    return response
