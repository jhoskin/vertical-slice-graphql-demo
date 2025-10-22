"""
GraphQL resolvers for onboard_trial workflow.
"""
import strawberry

from app.infrastructure.database.session import session_scope
from app.usecases.workflows.onboard_trial.handler import (
    get_onboarding_status_handler,
    onboard_trial_handler,
)
from app.usecases.workflows.onboard_trial.types import (
    OnboardTrialInput,
    OnboardTrialResponse,
    OnboardingStatusResponse,
)


@strawberry.mutation
def start_onboarding(input: OnboardTrialInput) -> OnboardTrialResponse:
    """
    GraphQL mutation to start trial onboarding workflow.

    Args:
        input: Onboarding input with trial, protocol, and sites

    Returns:
        Onboarding result with saga ID and state
    """
    with session_scope() as session:
        return onboard_trial_handler(session, input)


@strawberry.field
def onboarding_status(saga_id: int) -> OnboardingStatusResponse:
    """
    GraphQL query to check onboarding workflow status.

    Args:
        saga_id: ID of saga to check

    Returns:
        Current status of the workflow
    """
    with session_scope() as session:
        return get_onboarding_status_handler(session, saga_id)
