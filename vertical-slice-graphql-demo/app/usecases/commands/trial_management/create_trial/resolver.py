"""
GraphQL resolver for create_trial mutation.
"""
import strawberry

from app.infrastructure.database.session import session_scope
from app.usecases.commands.trial_management.create_trial.handler import create_trial_handler
from app.usecases.commands.trial_management.create_trial.types import (
    CreateTrialInput,
    CreateTrialResponse,
)


@strawberry.mutation
def create_trial(input: CreateTrialInput) -> CreateTrialResponse:
    """
    GraphQL mutation to create a new trial.

    Args:
        input: Trial creation input (validated via Pydantic)

    Returns:
        Created trial data
    """
    # Convert Strawberry-wrapped input to validated Pydantic model
    validated_input = input.to_pydantic()

    with session_scope() as session:
        return create_trial_handler(session, validated_input)
