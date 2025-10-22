"""
Handler for create_trial command.
"""
from sqlalchemy.orm import Session

from app.core.audit import audited
from app.infrastructure.database.models import Trial
from app.usecases.commands.trial_management._validation import validate_phase
from app.usecases.commands.trial_management.create_trial.types import (
    CreateTrialInput,
    CreateTrialOutput,
)


@audited(action="create_trial", entity="trial", entity_id_fn=lambda r: str(r.id))
def create_trial_handler(session: Session, input_data: CreateTrialInput) -> CreateTrialOutput:
    """
    Create a new trial.

    Args:
        session: Database session
        input_data: Trial creation input

    Returns:
        Created trial data

    Raises:
        ValidationError: If phase is invalid
    """
    # Validate phase using shared validation logic
    validate_phase(input_data.phase)

    # Create trial with status='draft'
    trial = Trial(
        name=input_data.name,
        phase=input_data.phase,
        status="draft",
    )

    session.add(trial)
    session.flush()  # Get ID without committing

    return CreateTrialOutput(
        id=trial.id,
        name=trial.name,
        phase=trial.phase,
        status=trial.status,
        created_at=trial.created_at,
    )
