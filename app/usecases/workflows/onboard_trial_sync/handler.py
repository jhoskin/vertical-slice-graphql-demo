"""
Handler for synchronous trial onboarding saga.

Implements saga pattern with in-memory compensation stack.
No state persistence - runs synchronously and blocks until complete.
"""
from sqlalchemy.orm import Session

from app.infrastructure.database.models import ProtocolVersion, Trial
from app.usecases.commands.register_site_to_trial.handler import (
    register_site_to_trial_handler,
)
from app.usecases.commands.register_site_to_trial.types import RegisterSiteToTrialInputModel
from app.usecases.commands.trial_management.create_trial.handler import (
    create_trial_handler,
)
from app.usecases.commands.trial_management.create_trial.types import CreateTrialInputModel
from app.usecases.workflows.onboard_trial_sync.types import (
    OnboardTrialSyncInputModel,
    OnboardTrialSyncResponse,
)


class SagaFailedError(Exception):
    """Raised when saga fails and compensations have been run."""
    pass


def onboard_trial_sync_handler(
    session: Session, input_data: OnboardTrialSyncInputModel
) -> OnboardTrialSyncResponse:
    """
    Synchronous saga for trial onboarding with compensation.

    Steps:
    1. Create trial
    2. Add protocol version
    3. Register sites

    If any step fails, all previous steps are compensated (rolled back).

    Args:
        session: Database session
        input_data: Onboarding input with trial, protocol, and sites

    Returns:
        Response with success status and trial ID

    Raises:
        SagaFailedError: If saga fails after running compensations
    """
    compensation_stack = []
    steps_completed = []
    trial_id = None

    try:
        # Step 1: Create trial
        trial_input = CreateTrialInputModel(
            name=input_data.name,
            phase=input_data.phase,
        )
        trial_response = create_trial_handler(session, trial_input)
        trial_id = trial_response.id
        steps_completed.append("create_trial")

        # Add compensation for trial creation
        def compensate_trial():
            trial = session.query(Trial).filter_by(id=trial_id).first()
            if trial:
                session.delete(trial)
                session.flush()

        compensation_stack.append(("delete_trial", compensate_trial))

        # Step 2: Add protocol version
        protocol = ProtocolVersion(
            trial_id=trial_id,
            version=input_data.initial_protocol_version,
            notes=f"Initial protocol for {input_data.name}",
        )
        session.add(protocol)
        session.flush()
        protocol_id = protocol.id
        steps_completed.append("add_protocol")

        # Add compensation for protocol
        def compensate_protocol():
            proto = session.query(ProtocolVersion).filter_by(id=protocol_id).first()
            if proto:
                session.delete(proto)
                session.flush()

        compensation_stack.append(("delete_protocol", compensate_protocol))

        # Step 3: Register sites
        site_ids = []
        for i, site_input in enumerate(input_data.sites):
            register_input = RegisterSiteToTrialInputModel(
                trial_id=trial_id,
                site_name=site_input.name,
                country=site_input.country,
            )
            site_response = register_site_to_trial_handler(session, register_input)
            site_ids.append(site_response.site_id)
            steps_completed.append(f"register_site_{i + 1}")

            # Add compensation for this site registration
            site_id_copy = site_response.site_id  # Capture in closure

            def compensate_site(sid=site_id_copy):
                # Delete trial_site link
                from app.infrastructure.database.models import TrialSite

                link = (
                    session.query(TrialSite)
                    .filter_by(trial_id=trial_id, site_id=sid)
                    .first()
                )
                if link:
                    session.delete(link)
                    session.flush()

            compensation_stack.append((f"unregister_site_{i + 1}", compensate_site))

        # All steps succeeded
        return OnboardTrialSyncResponse(
            success=True,
            trial_id=trial_id,
            message=f"Successfully onboarded trial '{input_data.name}' with {len(input_data.sites)} sites",
            steps_completed=steps_completed,
        )

    except Exception as e:
        # Saga failed - run compensations in reverse order
        compensation_errors = []

        for step_name, compensate_fn in reversed(compensation_stack):
            try:
                compensate_fn()
            except Exception as comp_error:
                # Log compensation errors but continue with other compensations
                compensation_errors.append(f"{step_name}: {str(comp_error)}")

        # Build error message
        error_msg = f"Saga failed at step '{steps_completed[-1] if steps_completed else 'unknown'}': {str(e)}"
        if compensation_errors:
            error_msg += f". Compensation errors: {'; '.join(compensation_errors)}"

        raise SagaFailedError(error_msg) from e
