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
    UpdateTrialMetadataOutput,
)


@strawberry.mutation
def update_trial_metadata(input: UpdateTrialMetadataInput) -> UpdateTrialMetadataOutput:
    """
    GraphQL mutation to update trial metadata.

    Args:
        input: Update input with trial_id and optional name/phase

    Returns:
        Updated trial data with change summary
    """
    with session_scope() as session:
        return update_trial_metadata_handler(session, input)
