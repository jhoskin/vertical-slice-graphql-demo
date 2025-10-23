"""
GraphQL resolver for synchronous trial onboarding saga.
"""
import strawberry

from app.infrastructure.database.session import session_scope
from app.usecases.workflows.onboard_trial_sync.handler import (
    onboard_trial_sync_handler,
)
from app.usecases.workflows.onboard_trial_sync.types import (
    OnboardTrialSyncInput,
    OnboardTrialSyncResponse,
)


@strawberry.mutation
def onboard_trial_sync(input: OnboardTrialSyncInput) -> OnboardTrialSyncResponse:
    """
    GraphQL mutation to onboard a trial synchronously using saga pattern.

    This mutation blocks until the entire saga completes or fails.
    If any step fails, all previous steps are automatically compensated.

    Args:
        input: Onboarding input with trial, protocol, and sites

    Returns:
        Response with success status and trial ID
    """
    with session_scope() as session:
        return onboard_trial_sync_handler(session, input)
