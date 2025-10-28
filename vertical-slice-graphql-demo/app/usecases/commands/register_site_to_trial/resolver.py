"""
GraphQL resolver for register_site_to_trial mutation.
"""
import strawberry

from app.infrastructure.database.session import session_scope
from app.usecases.commands.register_site_to_trial.handler import (
    register_site_to_trial_handler,
)
from app.usecases.commands.register_site_to_trial.types import (
    RegisterSiteToTrialInput,
    RegisterSiteToTrialResponse,
)


@strawberry.mutation
def register_site_to_trial(input: RegisterSiteToTrialInput) -> RegisterSiteToTrialResponse:
    """
    GraphQL mutation to register a site to a trial.

    Args:
        input: Site and trial information (validated via Pydantic)

    Returns:
        Registration result
    """
    # Convert GraphQL input to validated Pydantic model
    validated_input = input.to_pydantic()

    with session_scope() as session:
        return register_site_to_trial_handler(session, validated_input)
