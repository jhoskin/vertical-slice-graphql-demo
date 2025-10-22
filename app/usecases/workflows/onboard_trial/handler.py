"""
Handler for onboard_trial workflow (saga orchestration).
"""
from sqlalchemy.orm import Session

from app.core.audit import audited
from app.infrastructure.database.models import ProtocolVersion, SagaOnboardTrial
from app.usecases.commands.register_site_to_trial.handler import (
    register_site_to_trial_handler,
)
from app.usecases.commands.register_site_to_trial.types import RegisterSiteToTrialInput
from app.usecases.commands.trial_management.create_trial.handler import (
    create_trial_handler,
)
from app.usecases.commands.trial_management.create_trial.types import CreateTrialInput
from app.usecases.workflows.onboard_trial.types import (
    OnboardTrialInput,
    OnboardTrialResponse,
    OnboardingStatusResponse,
)


class SagaNotFoundError(Exception):
    """Raised when saga is not found."""
    pass


@audited(
    action="start_onboarding",
    entity="saga",
    entity_id_fn=lambda r: str(r.saga_id),
)
def onboard_trial_handler(
    session: Session, input_data: OnboardTrialInput
) -> OnboardTrialResponse:
    """
    Orchestrate trial onboarding workflow.

    This saga performs multiple steps:
    1. Create trial
    2. Add protocol version
    3. Register sites sequentially

    State transitions: STARTED → SITES_ADDED → COMPLETED | ERROR

    Args:
        session: Database session
        input_data: Onboarding input with trial info, protocol, and sites

    Returns:
        Onboarding result with saga ID and state
    """
    # Create saga record with STARTED state
    saga = SagaOnboardTrial(state="STARTED", trial_id=None, error=None)
    session.add(saga)
    session.flush()  # Get saga ID

    try:
        # Step 1: Create trial
        trial_input = CreateTrialInput(name=input_data.name, phase=input_data.phase)
        trial_output = create_trial_handler(session, trial_input)

        # Update saga with trial_id
        saga.trial_id = trial_output.id
        session.flush()

        # Step 2: Add protocol version
        protocol = ProtocolVersion(
            trial_id=trial_output.id,
            version=input_data.initial_protocol_version,
            notes="Initial protocol from onboarding",
        )
        session.add(protocol)
        session.flush()

        # Step 3: Register sites sequentially
        for site_input in input_data.sites:
            site_registration_input = RegisterSiteToTrialInput(
                trial_id=trial_output.id,
                site_name=site_input.name,
                country=site_input.country,
            )
            register_site_to_trial_handler(session, site_registration_input)

        # Update saga state to SITES_ADDED
        saga.state = "SITES_ADDED"
        session.flush()

        # Mark as COMPLETED
        saga.state = "COMPLETED"
        session.flush()

        return OnboardTrialResponse(
            saga_id=saga.id,
            trial_id=trial_output.id,
            state="COMPLETED",
            message=f"Successfully onboarded trial '{input_data.name}' with {len(input_data.sites)} sites",
        )

    except Exception as e:
        # Update saga state to ERROR
        saga.state = "ERROR"
        saga.error = str(e)
        session.flush()

        return OnboardTrialResponse(
            saga_id=saga.id,
            trial_id=saga.trial_id,
            state="ERROR",
            message=f"Onboarding failed: {str(e)}",
        )


def get_onboarding_status_handler(
    session: Session, saga_id: int
) -> OnboardingStatusResponse:
    """
    Get status of an onboarding workflow.

    Args:
        session: Database session
        saga_id: ID of saga to check

    Returns:
        Current status of the onboarding workflow

    Raises:
        SagaNotFoundError: If saga doesn't exist
    """
    saga = session.query(SagaOnboardTrial).filter_by(id=saga_id).first()

    if not saga:
        raise SagaNotFoundError(f"Saga with id {saga_id} not found")

    return OnboardingStatusResponse(
        saga_id=saga.id,
        trial_id=saga.trial_id,
        state=saga.state,
        error=saga.error,
        created_at=saga.created_at,
        updated_at=saga.updated_at,
    )
