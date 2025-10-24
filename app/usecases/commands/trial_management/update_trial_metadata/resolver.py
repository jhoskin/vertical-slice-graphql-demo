"""
GraphQL resolver for update_trial_metadata mutation.
"""
import strawberry

from app.infrastructure.database.session import session_scope
from app.usecases.commands.trial_management.update_trial_metadata.handler import (
    update_trial_metadata_handler,
)
from app.usecases.commands.trial_management.update_trial_metadata.types import (
    UpdateTrialMetadataInput,
    UpdateTrialMetadataResponse,
)


@strawberry.mutation
def update_trial_metadata(input: UpdateTrialMetadataInput) -> UpdateTrialMetadataResponse:
    """
    GraphQL mutation to update trial metadata.

    Args:
        input: Update input with trial_id, optional name/phase, and optional expected_version

    Returns:
        Updated trial data with change summary
    """
    # Convert Strawberry-wrapped input to validated Pydantic model
    validated_input = input.to_pydantic()

    with session_scope() as session:
        return update_trial_metadata_handler(session, validated_input)
