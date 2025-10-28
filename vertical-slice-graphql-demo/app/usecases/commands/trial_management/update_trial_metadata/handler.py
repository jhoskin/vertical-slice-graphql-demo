"""
Handler for update_trial_metadata command.
"""
from sqlalchemy.orm import Session

from app.core.audit import audited
from app.infrastructure.database.models import Trial
from app.usecases.commands.trial_management._errors import StaleDataError
from app.usecases.commands.trial_management._validation import (
    validate_phase,
    validate_phase_transition,
)
from app.usecases.commands.trial_management.update_trial_metadata.types import (
    UpdateTrialMetadataInputModel,
    UpdateTrialMetadataResponse,
)


class TrialNotFoundError(Exception):
    """Raised when trial is not found."""
    pass


@audited(action="update_trial_metadata", entity="trial", entity_id_fn=lambda r: str(r.id))
def update_trial_metadata_handler(
    session: Session, input_data: UpdateTrialMetadataInputModel
) -> UpdateTrialMetadataResponse:
    """
    Update trial metadata (name and/or phase).

    Args:
        session: Database session
        input_data: Update input with optional name, phase, and expected_updated_at

    Returns:
        Updated trial data with change summary

    Raises:
        TrialNotFoundError: If trial doesn't exist
        StaleDataError: If expected_updated_at doesn't match current updated_at
        ValidationError: If phase or phase transition is invalid
    """
    # Fetch trial
    trial = session.query(Trial).filter_by(id=input_data.trial_id).first()
    if not trial:
        raise TrialNotFoundError(f"Trial with id {input_data.trial_id} not found")

    # Check timestamp if provided (optimistic locking)
    if input_data.expected_updated_at is not None:
        # Compare timestamps - SQLite stores with microsecond precision
        if trial.updated_at != input_data.expected_updated_at:
            raise StaleDataError(
                f"Trial timestamp mismatch: expected {input_data.expected_updated_at.isoformat()}, "
                f"current is {trial.updated_at.isoformat()}. Please refresh and try again."
            )

    # Track changes
    changes = []

    # Update name if provided
    if input_data.name is not None and input_data.name != trial.name:
        old_name = trial.name
        trial.name = input_data.name
        changes.append(f"name: '{old_name}' -> '{trial.name}'")

    # Update phase if provided
    if input_data.phase is not None and input_data.phase != trial.phase:
        # Validate new phase
        validate_phase(input_data.phase)

        # Validate phase transition
        validate_phase_transition(trial.phase, input_data.phase)

        old_phase = trial.phase
        trial.phase = input_data.phase
        changes.append(f"phase: '{old_phase}' -> '{trial.phase}'")

    # Flush changes to database
    session.flush()

    # Refresh to get the updated_at value set by the database trigger
    session.refresh(trial)

    # Format changes summary
    changes_summary = "; ".join(changes) if changes else "no changes"

    return UpdateTrialMetadataResponse(
        id=trial.id,
        name=trial.name,
        phase=trial.phase,
        status=trial.status,
        updated_at=trial.updated_at,
        created_at=trial.created_at,
        changes=changes_summary,
    )
