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
    RegisterSiteToTrialOutput,
)


@strawberry.mutation
def register_site_to_trial(input: RegisterSiteToTrialInput) -> RegisterSiteToTrialOutput:
    """
    GraphQL mutation to register a site to a trial.

    Args:
        input: Site and trial information

    Returns:
        Registration result
    """
    with session_scope() as session:
        return register_site_to_trial_handler(session, input)
