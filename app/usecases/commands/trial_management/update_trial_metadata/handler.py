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
        input_data: Update input with optional name, phase, and expected_version

    Returns:
        Updated trial data with change summary

    Raises:
        TrialNotFoundError: If trial doesn't exist
        StaleDataError: If expected_version doesn't match current version
        ValidationError: If phase or phase transition is invalid
    """
    # Fetch trial
    trial = session.query(Trial).filter_by(id=input_data.trial_id).first()
    if not trial:
        raise TrialNotFoundError(f"Trial with id {input_data.trial_id} not found")

    # Check version if provided (optimistic locking)
    if input_data.expected_version is not None:
        if trial.version != input_data.expected_version:
            raise StaleDataError(
                f"Trial version mismatch: expected {input_data.expected_version}, "
                f"current is {trial.version}. Please refresh and try again."
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

    # Increment version on any change
    if changes:
        trial.version += 1

    session.flush()

    # Format changes summary
    changes_summary = "; ".join(changes) if changes else "no changes"

    return UpdateTrialMetadataResponse(
        id=trial.id,
        name=trial.name,
        phase=trial.phase,
        status=trial.status,
        version=trial.version,
        created_at=trial.created_at,
        changes=changes_summary,
    )
